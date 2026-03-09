from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel

class RoleType(str, Enum):
    ADMIN = "admin"
    BOAT_OWNER = "boat_owner"
    OFFICER = "officer"
    AGENT = "agent"
    BUYER = "buyer"

class RoleBase(BaseModel):
    name: RoleType

class Role(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
