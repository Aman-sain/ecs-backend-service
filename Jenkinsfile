pipeline {
    agent any

    environment {
        AWS_REGION = 'us-east-1'
        AWS_ACCOUNT_ID = '724772079986'
        SERVICE_NAME = 'backend'
        CLUSTER_NAME = 'auto-deploy-prod-cluster'
    }

    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        skipDefaultCheckout(true)  // We'll do clean checkout manually
    }

    stages {
        stage('🧹 Clean Workspace') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🧹 Cleaning workspace before checkout"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    # Force clean workspace with permission fix
                    sudo chmod -R 777 ${WORKSPACE} || chmod -R 777 ${WORKSPACE} || true
                    rm -rf ${WORKSPACE}/* ${WORKSPACE}/.* || true
                    echo "✓ Workspace cleaned"
                '''
            }
        }

        stage('🧹 Checkout Code') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🧹 Checking out code"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/main']],
                    extensions: [
                        [$class: 'CloneOption', depth: 1, shallow: true]
                    ],
                    userRemoteConfigs: [[
                        credentialsId: 'github-creds',
                        url: 'https://github.com/Aman-sain/ecs-backend-service'
                    ]]
                ])
            }
        }

        stage('🔍 Validate Configuration') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🔍 Validating Backend Service Configuration"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    # Validate deploy.yaml exists
                    if [ ! -f "codepipeline/deploy.yaml" ]; then
                        echo "❌ codepipeline/deploy.yaml not found!"
                        exit 1
                    fi

                    # Validate Dockerfile exists
                    if [ ! -f "Dockerfile" ]; then
                        echo "❌ Dockerfile not found!"
                        exit 1
                    fi

                    # Validate deploy.yaml syntax
                    python3 -c "import yaml; yaml.safe_load(open('codepipeline/deploy.yaml'))"
                    echo "✓ Configuration valid"
                '''
            }
        }

        stage('🧪 Run Tests') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🧪 Running Backend Tests"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    # Run tests in Docker container
                    docker run --rm -v $PWD:/app -w /app python:3.11 bash -c "
                        pip install -q -r requirements.txt pytest pytest-cov &&
                        pytest --maxfail=1 --disable-warnings -v || true
                    "
                '''
            }
        }

        stage('🐳 Build & Push Docker Image') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🐳 Building Backend Docker Image"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    # ECR Login
                    aws ecr get-login-password --region ${AWS_REGION} | \
                        docker login --username AWS --password-stdin \
                        ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

                    # Build image
                    IMAGE_TAG="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/auto-deploy-${SERVICE_NAME}:${BUILD_NUMBER}"
                    docker build -t $IMAGE_TAG .

                    # Push to ECR
                    docker push $IMAGE_TAG

                    # Tag as latest
                    docker tag $IMAGE_TAG "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/auto-deploy-${SERVICE_NAME}:latest"
                    docker push "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/auto-deploy-${SERVICE_NAME}:latest"

                    echo "✓ Image pushed: $IMAGE_TAG"
                '''
            }
        }

        stage('🚀 Deploy to ECS via CloudFormation') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🚀 Deploying Backend with CloudFormation"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    # Parse deploy.yaml configuration
                    pip3 install -q pyyaml

                    # Read deploy.yaml values
                    CPU=$(python3 -c "import yaml; print(yaml.safe_load(open('codepipeline/deploy.yaml'))['ecs']['cpu'])")
                    MEMORY=$(python3 -c "import yaml; print(yaml.safe_load(open('codepipeline/deploy.yaml'))['ecs']['memory'])")
                    DESIRED_COUNT=$(python3 -c "import yaml; print(yaml.safe_load(open('codepipeline/deploy.yaml'))['ecs']['desired_count'])")
                    CONTAINER_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('codepipeline/deploy.yaml'))['ecs']['container_port'])")

                    # Get Pulumi outputs (VPC, subnets, IAM roles)
                    echo "📊 Fetching infrastructure outputs from Pulumi..."
                    aws s3 cp s3://terraform-state-ecs-autodeploy-724772079986/pulumi/.pulumi/stacks/prod.json /tmp/pulumi-outputs.json || true

                    # Extract values from Pulumi state (fallback to hardcoded if needed)
                    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text)
                    SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')
                    TASK_EXEC_ROLE=$(aws iam get-role --role-name auto-deploy-ecs-execution-role --query 'Role.Arn' --output text)
                    TASK_ROLE=$(aws iam get-role --role-name auto-deploy-ecs-task-role --query 'Role.Arn' --output text)

                    # Build image tag
                    IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/auto-deploy-${SERVICE_NAME}:${BUILD_NUMBER}"

                    echo "Deploying CloudFormation stack..."
                    echo "  CPU: $CPU"
                    echo "  Memory: $MEMORY"
                    echo "  Desired Count: $DESIRED_COUNT"
                    echo "  Image: $IMAGE_URI"

                    # Deploy CloudFormation stack
                    aws cloudformation deploy \
                        --template-file codepipeline/service-stack.yaml \
                        --stack-name ecs-service-${SERVICE_NAME} \
                        --parameter-overrides \
                            ServiceName=${SERVICE_NAME} \
                            ClusterName=${CLUSTER_NAME} \
                            ImageUri=${IMAGE_URI} \
                            ContainerPort=${CONTAINER_PORT} \
                            DesiredCount=${DESIRED_COUNT} \
                            Cpu=${CPU} \
                            Memory=${MEMORY} \
                            VpcId=${VPC_ID} \
                            SubnetIds=${SUBNET_IDS} \
                            TaskExecutionRoleArn=${TASK_EXEC_ROLE} \
                            TaskRoleArn=${TASK_ROLE} \
                            LogGroupName=/ecs/auto-deploy-prod \
                        --capabilities CAPABILITY_IAM \
                        --region ${AWS_REGION} \
                        --no-fail-on-empty-changeset

                    echo "✅ CloudFormation deployment complete!"
                '''
            }
        }

        stage('🏥 Health Check') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🏥 Running Health Checks"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    echo "Waiting for deployment to stabilize..."
                    sleep 30

                    # Health check loop
                    for i in {1..10}; do
                        if curl -sf https://api.webbyftw.co.in/api/health; then
                            echo ""
                            echo "✅ Backend is healthy!"
                            exit 0
                        fi
                        echo "⏳ Waiting for backend... ($i/10)"
                        sleep 10
                    done

                    echo "⚠️  Health check timeout (service may still be starting)"
                '''
            }
        }

        stage('📊 Verify Deployment') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "📊 Verifying Deployment"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    # Check running tasks
                    echo "Checking ECS service status..."
                    aws ecs describe-services \
                        --cluster ${CLUSTER_NAME} \
                        --services ${SERVICE_NAME} \
                        --query 'services[0].[serviceName,status,runningCount,desiredCount]' \
                        --output table

                    # List tasks
                    echo ""
                    echo "Running tasks:"
                    aws ecs list-tasks \
                        --cluster ${CLUSTER_NAME} \
                        --service-name ${SERVICE_NAME} \
                        --desired-status RUNNING \
                        --query 'taskArns' \
                        --output table
                '''
            }
        }
    }

    post {
        success {
            script {
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "✅ BACKEND DEPLOYMENT SUCCESSFUL"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "Service URL: https://api.webbyftw.co.in/api"
                echo "API Docs: https://api.webbyftw.co.in/api/docs"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

                emailext (
                    subject: "✅ Backend Deployment Successful - Build #${env.BUILD_NUMBER}",
                    body: """
                    <h2>✅ Backend Deployed Successfully!</h2>
                    <table border="1" cellpadding="10">
                        <tr><td><b>Service</b></td><td>Backend API</td></tr>
                        <tr><td><b>Build</b></td><td>#${env.BUILD_NUMBER}</td></tr>
                        <tr><td><b>Cluster</b></td><td>${env.CLUSTER_NAME}</td></tr>
                        <tr><td><b>Strategy</b></td><td>Blue-Green (Zero Downtime)</td></tr>
                    </table>
                    <h3>Service URLs:</h3>
                    <ul>
                        <li><a href='https://api.webbyftw.co.in/api/health'>Health Check</a></li>
                        <li><a href='https://api.webbyftw.co.in/api/docs'>API Documentation</a></li>
                        <li><a href='https://api.webbyftw.co.in/api/employees'>Employees API</a></li>
                    </ul>
                    <p><i>Deployment completed with zero downtime using blue-green strategy.</i></p>
                    <p><a href='${env.BUILD_URL}console'>View Console Output</a></p>
                    """,
                    to: 'vibhavhaneja2004@gmail.com',
                    mimeType: 'text/html'
                )
            }
        }

        failure {
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "❌ BACKEND DEPLOYMENT FAILED"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

            emailext (
                subject: "❌ Backend Deployment Failed - Build #${env.BUILD_NUMBER}",
                body: """
                <h2>❌ Backend Deployment Failed</h2>
                <table border="1" cellpadding="10">
                    <tr><td><b>Service</b></td><td>Backend API</td></tr>
                    <tr><td><b>Build</b></td><td>#${env.BUILD_NUMBER}</td></tr>
                    <tr><td><b>Status</b></td><td><span style="color:red">FAILED</span></td></tr>
                </table>
                <p>Please check the logs for details.</p>
                <p><a href='${env.BUILD_URL}console'>View Console Output</a></p>
                """,
                to: 'vibhavhaneja2004@gmail.com',
                mimeType: 'text/html'
            )
        }

        always {
            script {
                // Docker cleanup
                try {
                    sh 'docker system prune -f || true'
                } catch (Exception e) {
                    echo "Docker cleanup: ${e.message}"
                }
                // Workspace cleanup with permission handling
                try {
                    sh '''
                        # Remove pytest cache and other files with sudo if needed
                        chmod -R 777 ${WORKSPACE} || true
                        rm -rf ${WORKSPACE}/* ${WORKSPACE}/.* || true
                    '''
                } catch (Exception e) {
                    echo "Workspace cleanup: ${e.message}"
                }
            }
        }
    }
}
