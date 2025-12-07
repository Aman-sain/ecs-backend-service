from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import employee_router, health_router
from core.config import settings
from db.init_db import init_database
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database with migration support
init_database()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Employee Management System API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(employee_router, prefix="/api/employees", tags=["employees"])

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.PROJECT_NAME}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
