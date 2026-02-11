import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "SHMS-Backend"
    API_V1_STR: str = "/api/v1"
    
    # APP
    APP_NAME: str = "face-recognition-system"
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    
    # JWT
    JWT_SECRET: str = "4d9c490cc2e8b264177708569502a9db4e1e86a0df6839a8"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # DATABASE
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "shms_db"
    
    # FACE
    FACE_MATCH_THRESHOLD: float = 0.40
    FACE_DUPLICATE_THRESHOLD: float = 0.30
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

