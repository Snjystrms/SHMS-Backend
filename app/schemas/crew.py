from typing import Optional
from pydantic import BaseModel

class CrewMemberBase(BaseModel):
    name: str
    aadhaar_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None

class CrewMemberCreate(CrewMemberBase):
    pass

class CrewMemberUpdate(BaseModel):
    name: Optional[str] = None
    aadhaar_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None

class CrewMemberResponse(CrewMemberBase):
    id: str
    
    class Config:
        from_attributes = True
