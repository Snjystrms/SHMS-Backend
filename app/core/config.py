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
    DB_SSLMODE: Optional[str] = None  # e.g. "require" for Neon; None = no SSL param
    
    # FACE
    FACE_MATCH_THRESHOLD: float = 0.40
    FACE_DUPLICATE_THRESHOLD: float = 0.30

    # SMS (forgot password OTP). Provider: mock | twilio | msg91 | fast2sms
    SMS_PROVIDER: str = "mock"
    SMS_OTP_EXPIRE_MINUTES: int = 2
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE: Optional[str] = None
    MSG91_AUTH_KEY: Optional[str] = None
    MSG91_SENDER_ID: Optional[str] = None
    FAST2SMS_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

