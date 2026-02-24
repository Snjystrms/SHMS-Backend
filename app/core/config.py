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
    # Distance threshold (pgvector <=>) for treating a face as a match
    FACE_MATCH_THRESHOLD: float = 0.40
    # Tighter distance threshold for treating a new registration as duplicate
    FACE_DUPLICATE_THRESHOLD: float = 0.30
    # InsightFace FaceAnalysis model configuration (pluggable via env)
    # Default uses ArcFace Buffalo_L pipeline as per FACE_RECOGNITION_SYSTEM_UPGRADE_2026.md
    FACE_MODEL_NAME: str = "buffalo_l"
    # GPU id for InsightFace (0 = first GPU, -1 = CPU)
    FACE_CTX_ID: int = 0

    # YOLO human detection (first stage filter for group images)
    YOLO_ENABLED: bool = True
    # Model name/path; e.g. "yolov8n.pt" / "yolo11n.pt" / custom
    YOLO_MODEL_NAME: str = "yolov8n.pt"
    # Confidence threshold for person detections
    YOLO_CONF_THRESHOLD: float = 0.25

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

