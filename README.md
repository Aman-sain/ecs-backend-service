# Backend Service

FastAPI backend service for Enterprise Employee Management System.

## 🚀 Tech Stack

- **FastAPI** (Python 3.11)
- **SQLAlchemy** ORM
- **Pydantic** validation
- **SQLite** database (production-ready for PostgreSQL)
- **Uvicorn** ASGI server

## 📋 API Endpoints

- `GET /api/health` - Health check
- `GET /api/employees` - List employees (with pagination & search)
- `GET /api/employees/{id}` - Get employee by ID
- `POST /api/employees` - Create employee
- `PUT /api/employees/{id}` - Update employee
- `DELETE /api/employees/{id}` - Delete employee
- `GET /api/employees/stats/summary` - Get statistics

## 🏗️ Project Structure

```
backend-service/
├── api/
│   └── routes.py          # API routes
├── db/
│   ├── database.py        # Database connection
│   └── models.py          # SQLAlchemy models
├── schemas/
│   └── employee.py        # Pydantic schemas
├── codepipeline/
│   └── deploy.yaml        # ECS deployment config
├── Dockerfile             # Production container
├── Jenkinsfile           # CI/CD pipeline
├── main.py               # Application entry point
└── requirements.txt      # Python dependencies
```

## 🔧 Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
python main.py
```

API will be available at: `http://localhost:8000`
API Docs: `http://localhost:8000/api/docs`

## 🐳 Docker

```bash
# Build
docker build -t backend .

# Run
docker run -p 8000:8000 backend
```

## 📝 Deployment Configuration

Edit `codepipeline/deploy.yaml`:

```yaml
service_name: backend
subdomain: api

ecs:
  cpu: 512                    # CPU units
  memory: 1024                # Memory in MB
  desired_count: 2            # Number of tasks
  container_port: 8000
  health_check_path: /api/health

environment:
  ENVIRONMENT: production
  DATABASE_URL: sqlite:///./employees.db

ssm_parameters:
  - /prod/backend/database-url
  - /prod/backend/secret-key
```

## 🚀 Deployment

### Via Jenkins (Recommended)
```bash
git add .
git commit -m "Updated API endpoint"
git push origin main
# Jenkins deploys automatically with zero downtime!
```

### Manual Deployment
```bash
python3 deploy.py
```

## 🔄 CI/CD Pipeline

Jenkins automatically:
1. Detects code changes
2. Builds Docker image
3. Pushes to ECR
4. Creates new ECS task definition
5. Deploys with blue-green strategy
6. Waits for health checks
7. Switches traffic (zero downtime!)
8. Sends email notification

**Deployment time**: ~5 minutes
**Downtime**: 0 seconds

## 🏥 Health Check

```bash
curl https://api.webbyftw.co.in/api/health
```

## 📊 Monitoring

```bash
# View logs
aws logs tail /ecs/auto-deploy-prod --follow --filter-pattern "backend"

# Check service status
aws ecs describe-services \
  --cluster auto-deploy-prod-cluster \
  --service backend
```

## 🔐 Environment Variables

- `DATABASE_URL` - Database connection string
- `ENVIRONMENT` - Environment name (development/production)
- `PROJECT_NAME` - Project name

**Secrets** are stored in AWS SSM Parameter Store.

## 🧪 Testing

```bash
pytest
```

## 📚 API Documentation

Auto-generated docs available at:
- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`

## 🌐 Service URL

**Production**: https://api.webbyftw.co.in/api

---

**Maintained by Backend Team**
