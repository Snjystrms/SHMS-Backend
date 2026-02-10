from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr


class RoleType(str, Enum):
    ADMIN = "admin"
    BOAT_OWNER = "boat_owner"
    OFFICER = "officer"


class Role(BaseModel):
    id: int
    name: RoleType
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class User(BaseModel):
    id: str  # you are currently using UUID strings for user IDs
    name: str
    email: EmailStr
    phone: str
    password: str
    role_id: int  # FK to Role.id
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str


class CrewMember(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: str
    role_id: int  # FK to Role.id
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class CrewFaceEmbedding(BaseModel):
    id: str
    crew_member_id: str  # FK to CrewMember.id
    embedding: list[float]
    created_at: datetime
    updated_at: datetime

