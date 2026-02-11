from typing import Optional
from pydantic import BaseModel


class UserInfo(BaseModel):
    """User information returned in login response."""
    id: str
    name: str
    email: str
    role: str


class Token(BaseModel):
    """Token response with user information."""
    access_token: str
    token_type: str
    user: UserInfo


class TokenData(BaseModel):
    """Token payload data."""
    id: Optional[str] = None
    role: Optional[str] = None

