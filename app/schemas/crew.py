from typing import Optional, List
from pydantic import BaseModel


class CrewVerifyOtpRequest(BaseModel):
    """Request body for crew member OTP verification (after submit)."""
    mobile_number: str
    otp: str


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


class CrewFaceScanResult(BaseModel):
    """One detected face and its match (if any). No bbox in response; boxes are on annotated_image_url only."""
    det_score: float
    distance: Optional[float] = None
    is_match: bool
    crew_member: Optional[CrewMemberResponse] = None


class CrewGroupScanResponse(BaseModel):
    """Response for group photo scan (crew identification)."""
    faces: List[CrewFaceScanResult]
    total_faces: int
    matched_count: int
    unmatched_count: int
    annotated_image_url: Optional[str] = None  # URL to GET the processed PNG (green=match, red=no match). One-time use.
