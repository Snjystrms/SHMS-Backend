from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
import jwt
import bcrypt
from app.core.config import settings

def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a password."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=getattr(settings, "BCRYPT_ROUNDS", 10))
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verify a plain-text password against its hashed version."""
    if hashed_password is None or not hashed_password:
        return False
    # Handle plain text for now if not hashed (for initial migration)
    if not (hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$")):
        return plain_password == hashed_password
    
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


PASSWORD_RESET_PURPOSE = "password_reset"


def create_password_reset_token(user_id: Union[str, int]) -> str:
    """Short-lived JWT for password reset. Use decode_password_reset_token in reset-password."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    to_encode = {"exp": expire, "sub": str(user_id), "purpose": PASSWORD_RESET_PURPOSE}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_password_reset_token(token: str) -> Optional[str]:
    """Decode and validate reset token. Returns user_id or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("purpose") != PASSWORD_RESET_PURPOSE:
            return None
        return payload.get("sub")
    except Exception:
        return None

