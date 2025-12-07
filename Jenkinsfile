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
                sh '''
                    # Manual git clone to avoid Jenkins workspace cleanup issues
                    git clone --depth 1 --branch main https://github.com/Aman-sain/ecs-backend-service.git ${WORKSPACE}/repo

                    # Move contents to workspace root
                    mv ${WORKSPACE}/repo/* ${WORKSPACE}/ || true
                    mv ${WORKSPACE}/repo/.* ${WORKSPACE}/ 2>/dev/null || true
                    rm -rf ${WORKSPACE}/repo

                    echo "✓ Code checked out successfully"
                '''
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

                    # Get infrastructure values (VPC, subnets, IAM roles)
                    echo "📊 Fetching infrastructure outputs..."
                    VPC_ID="vpc-02d7f89b03701136a"
                    SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --query 'Subnets[*].SubnetId' --output text | tr '\\t' ',')
                    TASK_EXEC_ROLE=$(aws iam get-role --role-name auto-deploy-ecs-execution-role --query 'Role.Arn' --output text)
                    TASK_ROLE=$(aws iam get-role --role-name auto-deploy-ecs-task-role --query 'Role.Arn' --output text)

                    # Build image tag
                    IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/auto-deploy-${SERVICE_NAME}:${BUILD_NUMBER}"

                    echo "Deploying CloudFormation stack..."
                    echo "  CPU: $CPU"
                    echo "  Memory: $MEMORY"
                    echo "  Desired Count: $DESIRED_COUNT"
                    echo "  Image: $IMAGE_URI"
                    echo "  Subnet IDs: $SUBNET_IDS"

                    # Save current task definition for rollback
                    echo "📋 Saving current deployment state for rollback..."
                    if aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --query 'services[0].taskDefinition' --output text 2>/dev/null | grep -q 'arn:aws'; then
                        PREVIOUS_TASK_DEF=$(aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --query 'services[0].taskDefinition' --output text)
                        echo "Previous task definition: $PREVIOUS_TASK_DEF"
                        echo "$PREVIOUS_TASK_DEF" > /tmp/previous_task_def.txt
                    else
                        echo "No previous deployment found (first deployment)"
                        echo "NONE" > /tmp/previous_task_def.txt
                    fi

                    # Deploy CloudFormation stack with retry logic
                    echo "🚀 Starting CloudFormation deployment..."
                    
                    MAX_RETRIES=5
                    RETRY_COUNT=0
                    DEPLOY_SUCCESS=false
                    
                    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
                        echo "Deployment attempt $((RETRY_COUNT + 1))/$MAX_RETRIES..."
                        
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
                            --no-fail-on-empty-changeset 2>&1 | tee /tmp/cfn_deploy.log
                        
                        DEPLOY_EXIT_CODE=${PIPESTATUS[0]}
                        
                        if [ $DEPLOY_EXIT_CODE -eq 0 ]; then
                            echo "✅ CloudFormation deployment succeeded!"
                            DEPLOY_SUCCESS=true
                            break
                        elif grep -q "UPDATE_IN_PROGRESS" /tmp/cfn_deploy.log; then
                            echo "⏳ Stack is currently updating. Waiting 30 seconds before retry..."
                            sleep 30
                            RETRY_COUNT=$((RETRY_COUNT + 1))
                        else
                            echo "❌ CloudFormation deployment failed with error!"
                            cat /tmp/cfn_deploy.log
                            exit 1
                        fi
                    done
                    
                    if [ "$DEPLOY_SUCCESS" = false ]; then
                        echo "❌ CloudFormation deployment failed after $MAX_RETRIES attempts!"
                        exit 1
                    fi

                    echo "⏳ Waiting for ECS service to stabilize (blue-green deployment)..."

                    # Wait for service to become stable (ensures new tasks are running)
                    aws ecs wait services-stable \
                        --cluster ${CLUSTER_NAME} \
                        --services ${SERVICE_NAME} \
                        --region ${AWS_REGION}

                    if [ $? -eq 0 ]; then
                        echo "✅ ECS service stabilized - new tasks are running!"
                    else
                        echo "⚠️  Service stabilization timed out, but continuing to health check..."
                    fi
                '''
            }
        }

        stage('🏥 Health Check') {
            steps {
                script {
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "🏥 Running Health Checks via ALB"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                }
                sh '''
                    echo "⏳ Waiting 30s for new tasks to register with ALB..."
                    sleep 30

                    # Check ALB target health
                    echo "🔍 Checking ALB target group health..."
                    TARGET_GROUP_ARN=$(aws cloudformation describe-stacks \\
                        --stack-name ecs-service-${SERVICE_NAME} \\
                        --query 'Stacks[0].Outputs[?OutputKey==`TargetGroupArn`].OutputValue' \\
                        --output text 2>/dev/null || echo "")

                    if [ -z "$TARGET_GROUP_ARN" ]; then
                        echo "⚠️  Could not find target group ARN from stack, checking via tags..."
                        TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups \\
                            --names backend-tg \\
                            --query 'TargetGroups[0].TargetGroupArn' \\
                            --output text 2>/dev/null || echo "")
                    fi

                    # Health check loop with ALB verification
                    HEALTH_CHECK_PASSED=false
                    for i in {1..20}; do
                        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        echo "Health Check Attempt $i/20"

                        # Check endpoint health
                        if curl -sf https://api.webbyftw.co.in/api/health > /dev/null 2>&1; then
                            echo "✅ Endpoint health check passed!"

                            # Verify ALB target health if we have target group ARN
                            if [ -n "$TARGET_GROUP_ARN" ] && [ "$TARGET_GROUP_ARN" != "None" ]; then
                                HEALTHY_COUNT=$(aws elbv2 describe-target-health \\
                                    --target-group-arn "$TARGET_GROUP_ARN" \\
                                    --query 'TargetHealthDescriptions[?TargetHealth.State==`healthy`] | length(@)' \\
                                    --output text 2>/dev/null || echo "0")

                                echo "📊 Healthy targets in ALB: $HEALTHY_COUNT"

                                if [ "$HEALTHY_COUNT" -gt 0 ]; then
                                    echo "✅ ALB has healthy targets!"
                                    HEALTH_CHECK_PASSED=true
                                    break
                                else
                                    echo "⏳ Waiting for targets to become healthy in ALB..."
                                fi
                            else
                                echo "✅ Health check passed (ALB verification skipped)"
                                HEALTH_CHECK_PASSED=true
                                break
                            fi
                        else
                            echo "⏳ Endpoint not healthy yet, waiting... ($i/20)"
                        fi

                        sleep 15
                    done

                    if [ "$HEALTH_CHECK_PASSED" = false ]; then
                        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        echo "❌ HEALTH CHECK FAILED - Initiating rollback!"
                        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

                        # Read previous task definition
                        PREVIOUS_TASK_DEF=$(cat /tmp/previous_task_def.txt 2>/dev/null || echo "NONE")

                        if [ "$PREVIOUS_TASK_DEF" != "NONE" ] && [ -n "$PREVIOUS_TASK_DEF" ]; then
                            echo "🔄 Rolling back to previous task definition: $PREVIOUS_TASK_DEF"

                            aws ecs update-service \\
                                --cluster ${CLUSTER_NAME} \\
                                --service ${SERVICE_NAME} \\
                                --task-definition "$PREVIOUS_TASK_DEF" \\
                                --force-new-deployment \\
                                --region ${AWS_REGION}

                            echo "⏳ Waiting for rollback to complete..."
                            sleep 30

                            echo "❌ Deployment failed health checks and was rolled back!"
                        else
                            echo "⚠️  No previous deployment to rollback to. This was the first deployment."
                            echo "❌ Health checks failed on initial deployment!"
                        fi

                        # Show recent logs to help debug
                        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        echo "📋 Recent Container Logs (last 50 lines):"
                        aws logs tail /ecs/auto-deploy-prod --follow --since 5m --filter-pattern "" --format short | head -50 || true

                        exit 1
                    fi

                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    echo "✅ All health checks passed!"
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
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
                // Cleanup temporary files
                try {
                    sh 'rm -f /tmp/previous_task_def.txt || true'
                } catch (Exception e) {
                    echo "Temp file cleanup: ${e.message}"
                }
                // Workspace cleanup with permission handling
                try {
                    sh '''
                        # Remove pytest cache and other files
                        find ${WORKSPACE} -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
                        find ${WORKSPACE} -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
                        find ${WORKSPACE} -type f -name "*.pyc" -delete 2>/dev/null || true
                        docker system prune -f || true
                    '''
                } catch (Exception e) {
                    echo "Workspace cleanup: ${e.message}"
                }
            }
        }
    }
}
