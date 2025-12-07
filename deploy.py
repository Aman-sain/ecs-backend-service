#!/usr/bin/env python3
"""
ECS Blue-Green Deployment Script
Reads deploy.yaml, builds Docker image, pushes to ECR, and deploys with zero downtime
"""

import os
import sys
import yaml
import json
import boto3
import subprocess
import time
from datetime import datetime

class ECSDeployer:
    def __init__(self, config_path="codepipeline/deploy.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.ecs = boto3.client('ecs')
        self.elbv2 = boto3.client('elbv2')
        self.ecr = boto3.client('ecr')
        self.ssm = boto3.client('ssm')
        self.route53 = boto3.client('route53')
        self.sts = boto3.client('sts')

        self.account_id = self.sts.get_caller_identity()['Account']
        self.region = os.environ.get('AWS_REGION', 'us-east-1')

    def load_config(self):
        """Load deployment configuration from deploy.yaml"""
        if not os.path.exists(self.config_path):
            print(f"Error: {self.config_path} not found")
            sys.exit(1)

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Validate required fields
        required = ['service_name', 'ecs']
        for field in required:
            if field not in config:
                print(f"Error: Missing required field '{field}' in deploy.yaml")
                sys.exit(1)

        return config

    def get_ssm_parameters(self):
        """Fetch SSM parameters defined in config"""
        ssm_params = []
        if 'ssm_parameters' in self.config:
            for param_name in self.config['ssm_parameters']:
                try:
                    response = self.ssm.get_parameter(Name=param_name, WithDecryption=True)
                    ssm_params.append({
                        'name': param_name.split('/')[-1].upper().replace('-', '_'),
                        'valueFrom': response['Parameter']['ARN']
                    })
                except Exception as e:
                    print(f"Warning: Could not fetch SSM parameter {param_name}: {e}")

        return ssm_params

    def build_and_push_image(self):
        """Build Docker image and push to ECR"""
        service_name = self.config['service_name']
        repo_name = f"auto-deploy-{service_name}"

        # Get ECR login
        print(f"[{datetime.now()}] Logging into ECR...")
        login_cmd = f"aws ecr get-login-password --region {self.region} | docker login --username AWS --password-stdin {self.account_id}.dkr.ecr.{self.region}.amazonaws.com"
        subprocess.run(login_cmd, shell=True, check=True)

        # Create repo if doesn't exist
        try:
            self.ecr.describe_repositories(repositoryNames=[repo_name])
        except self.ecr.exceptions.RepositoryNotFoundException:
            print(f"[{datetime.now()}] Creating ECR repository {repo_name}...")
            self.ecr.create_repository(repositoryName=repo_name)

        # Build image
        image_tag = f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{repo_name}:{int(time.time())}"
        print(f"[{datetime.now()}] Building Docker image {image_tag}...")

        build_cmd = f"docker build -t {image_tag} ."
        subprocess.run(build_cmd, shell=True, check=True)

        # Push image
        print(f"[{datetime.now()}] Pushing image to ECR...")
        push_cmd = f"docker push {image_tag}"
        subprocess.run(push_cmd, shell=True, check=True)

        return image_tag

    def create_task_definition(self, image_uri):
        """Create ECS task definition"""
        ecs_config = self.config['ecs']
        service_name = self.config['service_name']

        # Get SSM parameters
        secrets = self.get_ssm_parameters()

        # Environment variables
        environment = [{'name': k, 'value': str(v)} for k, v in self.config.get('environment', {}).items()]

        task_def = {
            'family': f"auto-deploy-{service_name}",
            'networkMode': 'awsvpc',
            'requiresCompatibilities': ['FARGATE'],
            'cpu': str(ecs_config.get('cpu', 256)),
            'memory': str(ecs_config.get('memory', 512)),
            'executionRoleArn': f"arn:aws:iam::{self.account_id}:role/auto-deploy-ecs-exec-*",
            'taskRoleArn': f"arn:aws:iam::{self.account_id}:role/auto-deploy-ecs-task-*",
            'containerDefinitions': [{
                'name': service_name,
                'image': image_uri,
                'portMappings': [{
                    'containerPort': ecs_config.get('container_port', 8080),
                    'protocol': 'tcp'
                }],
                'environment': environment,
                'secrets': secrets,
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': '/ecs/auto-deploy-prod',
                        'awslogs-region': self.region,
                        'awslogs-stream-prefix': service_name
                    }
                },
                'healthCheck': {
                    'command': ['CMD-SHELL', f"curl -f http://localhost:{ecs_config.get('container_port', 8080)}{ecs_config.get('health_check_path', '/health')} || exit 1"],
                    'interval': 30,
                    'timeout': 5,
                    'retries': 3,
                    'startPeriod': 60
                }
            }]
        }

        print(f"[{datetime.now()}] Registering task definition...")
        response = self.ecs.register_task_definition(**task_def)
        return response['taskDefinition']['taskDefinitionArn']

    def get_vpc_config(self):
        """Get VPC configuration from existing resources"""
        ec2 = boto3.client('ec2')

        # Find VPC by tag
        vpcs = ec2.describe_vpcs(Filters=[
            {'Name': 'tag:Name', 'Values': ['auto-deploy-prod-vpc']}
        ])

        if not vpcs['Vpcs']:
            print("Error: VPC not found. Run terraform apply first.")
            sys.exit(1)

        vpc_id = vpcs['Vpcs'][0]['VpcId']

        # Get private subnets
        subnets = ec2.describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]},
            {'Name': 'tag:Type', 'Values': ['private']}
        ])
        subnet_ids = [s['SubnetId'] for s in subnets['Subnets']]

        # Get ECS security group
        sgs = ec2.describe_security_groups(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]},
            {'Name': 'tag:Name', 'Values': ['auto-deploy-prod-ecs-tasks-sg']}
        ])
        sg_id = sgs['SecurityGroups'][0]['GroupId'] if sgs['SecurityGroups'] else None

        return {
            'subnets': subnet_ids,
            'securityGroups': [sg_id],
            'assignPublicIp': 'DISABLED'
        }

    def create_target_group(self):
        """Create new target group for blue-green deployment"""
        service_name = self.config['service_name']
        ecs_config = self.config['ecs']

        # Get VPC ID - try multiple methods
        ec2 = boto3.client('ec2')

        # Method 1: Try by tag
        vpcs = ec2.describe_vpcs(Filters=[
            {'Name': 'tag:Name', 'Values': ['auto-deploy-prod-vpc']}
        ])

        if not vpcs['Vpcs']:
            # Method 2: Try by CIDR (our created VPC)
            vpcs = ec2.describe_vpcs(Filters=[
                {'Name': 'cidr-block', 'Values': ['10.100.0.0/16']}
            ])

        if not vpcs['Vpcs']:
            # Method 3: Use default VPC
            vpcs = ec2.describe_vpcs(Filters=[
                {'Name': 'isDefault', 'Values': ['true']}
            ])

        if not vpcs['Vpcs']:
            # Method 4: Get any VPC
            vpcs = ec2.describe_vpcs()

        if not vpcs['Vpcs']:
            raise Exception("No VPC found in us-east-1! Please run infrastructure pipeline first.")

        vpc_id = vpcs['Vpcs'][0]['VpcId']
        print(f"[{datetime.now()}] Using VPC: {vpc_id}")

        tg_name = f"auto-{service_name}-{int(time.time())}"[:32]

        print(f"[{datetime.now()}] Creating target group {tg_name}...")
        response = self.elbv2.create_target_group(
            Name=tg_name,
            Protocol='HTTP',
            Port=ecs_config.get('container_port', 8080),
            VpcId=vpc_id,
            HealthCheckEnabled=True,
            HealthCheckProtocol='HTTP',
            HealthCheckPath=ecs_config.get('health_check_path', '/health'),
            HealthCheckIntervalSeconds=30,
            HealthCheckTimeoutSeconds=5,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=3,
            TargetType='ip',
            Tags=[
                {'Key': 'Service', 'Value': service_name},
                {'Key': 'Deployment', 'Value': 'blue-green'}
            ]
        )

        return response['TargetGroups'][0]['TargetGroupArn']

    def create_or_update_service(self, task_definition_arn, target_group_arn):
        """Create or update ECS service"""
        service_name = self.config['service_name']
        ecs_config = self.config['ecs']
        cluster_name = 'auto-deploy-prod-cluster'

        service_config = {
            'cluster': cluster_name,
            'serviceName': service_name,
            'taskDefinition': task_definition_arn,
            'desiredCount': ecs_config.get('desired_count', 1),
            'launchType': 'FARGATE',
            'networkConfiguration': {
                'awsvpcConfiguration': self.get_vpc_config()
            },
            'loadBalancers': [{
                'targetGroupArn': target_group_arn,
                'containerName': service_name,
                'containerPort': ecs_config.get('container_port', 8080)
            }],
            'healthCheckGracePeriodSeconds': 60
        }

        try:
            # Check if service exists
            self.ecs.describe_services(cluster=cluster_name, services=[service_name])

            print(f"[{datetime.now()}] Updating service {service_name}...")
            self.ecs.update_service(
                cluster=cluster_name,
                service=service_name,
                taskDefinition=task_definition_arn,
                forceNewDeployment=True
            )
        except:
            print(f"[{datetime.now()}] Creating service {service_name}...")
            self.ecs.create_service(**service_config)

        return service_name

    def wait_for_service_stable(self, service_name):
        """Wait for service to be stable"""
        cluster_name = 'auto-deploy-prod-cluster'
        print(f"[{datetime.now()}] Waiting for service to be stable...")

        waiter = self.ecs.get_waiter('services_stable')
        waiter.wait(
            cluster=cluster_name,
            services=[service_name],
            WaiterConfig={'Delay': 15, 'MaxAttempts': 40}
        )

        print(f"[{datetime.now()}] Service is stable!")

    def update_alb_listener(self, target_group_arn):
        """Update ALB listener to point to new target group"""
        service_name = self.config['service_name']
        subdomain = self.config.get('subdomain', service_name)
        domain = 'webbyftw.co.in'
        host_header = f"{subdomain}.{domain}"

        # Find ALB listener
        albs = self.elbv2.describe_load_balancers(Names=['auto-deploy-prod-alb'])
        alb_arn = albs['LoadBalancers'][0]['LoadBalancerArn']

        listeners = self.elbv2.describe_listeners(LoadBalancerArn=alb_arn)
        https_listener = [l for l in listeners['Listeners'] if l['Port'] == 443][0]

        print(f"[{datetime.now()}] Updating ALB listener rule for {host_header}...")

        # Check if rule exists
        rules = self.elbv2.describe_rules(ListenerArn=https_listener['ListenerArn'])
        existing_rule = None

        for rule in rules['Rules']:
            for condition in rule.get('Conditions', []):
                if condition.get('Field') == 'host-header':
                    if host_header in condition.get('Values', []):
                        existing_rule = rule
                        break

        if existing_rule and existing_rule['RuleArn'] != 'default':
            # Update existing rule
            self.elbv2.modify_rule(
                RuleArn=existing_rule['RuleArn'],
                Actions=[{
                    'Type': 'forward',
                    'TargetGroupArn': target_group_arn
                }]
            )
        else:
            # Create new rule
            priority = int(time.time()) % 50000
            self.elbv2.create_rule(
                ListenerArn=https_listener['ListenerArn'],
                Priority=priority,
                Conditions=[{
                    'Field': 'host-header',
                    'Values': [host_header]
                }],
                Actions=[{
                    'Type': 'forward',
                    'TargetGroupArn': target_group_arn
                }]
            )

    def cleanup_old_target_groups(self):
        """Remove old target groups for this service"""
        service_name = self.config['service_name']

        print(f"[{datetime.now()}] Cleaning up old target groups...")

        tgs = self.elbv2.describe_target_groups()
        for tg in tgs['TargetGroups']:
            if tg['TargetGroupName'].startswith(f"auto-{service_name}-"):
                # Check if it's old (not in use)
                try:
                    # Get target health
                    health = self.elbv2.describe_target_health(TargetGroupArn=tg['TargetGroupArn'])

                    # Delete if no targets or all unhealthy
                    if not health['TargetHealthDescriptions']:
                        print(f"  Deleting unused target group {tg['TargetGroupName']}...")
                        self.elbv2.delete_target_group(TargetGroupArn=tg['TargetGroupArn'])
                except:
                    pass

    def deploy(self):
        """Execute full blue-green deployment"""
        print(f"\n{'='*60}")
        print(f"Starting deployment for {self.config['service_name']}")
        print(f"{'='*60}\n")

        # Step 1: Build and push image
        image_uri = self.build_and_push_image()

        # Step 2: Create task definition
        task_def_arn = self.create_task_definition(image_uri)

        # Step 3: Create new target group
        target_group_arn = self.create_target_group()

        # Step 4: Create or update service
        service_name = self.create_or_update_service(task_def_arn, target_group_arn)

        # Step 5: Wait for service to be healthy
        self.wait_for_service_stable(service_name)

        # Step 6: Update ALB to point to new target group
        self.update_alb_listener(target_group_arn)

        # Step 7: Cleanup old resources
        time.sleep(30)  # Wait a bit before cleanup
        self.cleanup_old_target_groups()

        subdomain = self.config.get('subdomain', self.config['service_name'])
        print(f"\n{'='*60}")
        print(f"Deployment successful!")
        print(f"Service URL: https://{subdomain}.webbyftw.co.in")
        print(f"{'='*60}\n")

if __name__ == '__main__':
    deployer = ECSDeployer()
    deployer.deploy()
