from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise Employee Management System"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./employees.db"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]

    # API
    API_V1_PREFIX: str = "/api/v1"

    class Config:
        case_sensitive = True


settings = Settings()
