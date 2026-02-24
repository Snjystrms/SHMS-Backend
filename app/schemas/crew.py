from typing import Optional
from pydantic import BaseModel

class CrewMemberBase(BaseModel):
    name: str
    aadhaar_number: Optional[str] = None
    contact_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    is_pilot: bool = False

class CrewMemberCreate(CrewMemberBase):
    pass

class CrewMemberUpdate(BaseModel):
    name: Optional[str] = None
    aadhaar_number: Optional[str] = None
    contact_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    is_pilot: Optional[bool] = None

class CrewMemberResponse(CrewMemberBase):
    id: str
    
    class Config:
        from_attributes = True
