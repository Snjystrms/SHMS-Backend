from typing import Generator, Dict
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings
from app.db.session import get_db_connection
from app.services import user_service as crud_user

bearer_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")

        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = crud_user.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user

def get_admin_user(current_user: Dict = Depends(get_current_user)) -> Dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user

def get_admin_or_officer_user(
    current_user: Dict = Depends(get_current_user),
) -> Dict:
    role = current_user.get("role")
    if role not in ["admin", "officer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user


def get_boat_owner_user(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Require current user to be a boat_owner."""
    if current_user.get("role") != "boat_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Boat owner access required",
        )
    return current_user


def get_agent_user(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Require current user to be an agent."""
    if current_user.get("role") != "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent access required",
        )
    return current_user
