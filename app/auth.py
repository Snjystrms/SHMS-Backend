import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Union
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.database import conn

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET", "4d9c490cc2e8b264177708569502a9db4e1e86a0df6839a8") # Random fallback
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hashed version."""
    # Handle plain text for now if not hashed (for initial migration)
    if not (hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$")):
        return plain_password == hashed_password
    
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a password."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get the current user from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    # Fetch user from database
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, role_id FROM users WHERE id = %s AND deleted_at IS NULL", (user_id,))
    user = cur.fetchone()
    if user is None:
        raise credentials_exception
    
    return {
        "id": user[0],
        "name": user[1],
        "email": user[2],
        "role_id": user[3]
    }

async def get_admin_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure the current user is an admin."""
    # Get role name from roles table
    cur = conn.cursor()
    cur.execute("SELECT name FROM roles WHERE id = %s", (current_user["role_id"],))
    role = cur.fetchone()
    
    if not role or role[0] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user
