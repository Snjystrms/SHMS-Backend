import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "SHMS-Backend"
    API_V1_STR: str = "/api/v1"

    # Public URL for absolute image URLs (required when behind reverse proxy).
    # If set, image URLs use this instead of request.base_url.
    # Example: https://api.example.com
    PUBLIC_URL: Optional[str] = None
    
    # APP
    APP_NAME: str = "face-recognition-system"
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    
    # JWT
    JWT_SECRET: str = "4d9c490cc2e8b264177708569502a9db4e1e86a0df6839a8"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Bcrypt: 10 rounds ~100ms vs 12 rounds ~350ms per verify. Still secure.
    BCRYPT_ROUNDS: int = 10

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
    FACE_MODEL_NAME: str = "buffalo_s"
    # GPU id for InsightFace (0 = first GPU, -1 = CPU)
    FACE_CTX_ID: int = -1

    # YOLO human detection (first stage filter for group images)
    YOLO_ENABLED: bool = True
    # Model name/path; e.g. "yolo26n.pt" (YOLO26 nano) / "yolo26s.pt" / custom
    YOLO_MODEL_NAME: str = "yolo26n.pt"
    # Confidence threshold for person detections
    YOLO_CONF_THRESHOLD: float = 0.25
    # Max image side used for detection/embedding pre-processing in group scans.
    # Lower values reduce latency at possible accuracy tradeoff.
    FACE_DETECT_MAX_SIDE: int = 512
    # If true, persist scan artifacts (annotated image/crops/embeddings) in background.
    # This reduces request latency for /crew-members/scan-group-photo.
    SCAN_ASYNC_PERSISTENCE: bool = True

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

