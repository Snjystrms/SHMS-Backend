from typing import Optional, List, Literal
from pydantic import BaseModel


class CrewVerifyOtpRequest(BaseModel):
    """Request body for crew member OTP verification (after submit)."""
    mobile_number: str
    otp: str


class OfficerRegisterUserRequest(BaseModel):
    """Officer registers a user with minimum info. Only name and aadhaar are required; is_register is always false."""
    name: str
    aadhaar_number: str
    contact_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    is_pilot: bool = False
    crop_image_url: Optional[str] = None


class CrewMemberBase(BaseModel):
    name: str
    aadhaar_number: Optional[str] = None
    contact_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    is_pilot: bool = False
    is_register: bool = False

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
    is_register: bool = False

    class Config:
        from_attributes = True


class CrewFaceScanResult(BaseModel):
    """One detected face and its match (if any). No bbox in response; boxes are on annotated_image_url only."""
    det_score: float
    distance: Optional[float] = None
    is_match: bool
    crew_member: Optional[CrewMemberResponse] = None
    crop_id: Optional[str] = None  # UUID for crew face crop; use when attaching crew to movement for image_url in history.
    crop_image_url: Optional[str] = None  # One-time URL to GET the cropped face/person PNG for frontend display.


class CrewGroupScanResponse(BaseModel):
    """Response for group photo scan (crew identification)."""
    faces: List[CrewFaceScanResult]
    total_faces: int
    matched_count: int
    unmatched_count: int
    annotated_image_url: Optional[str] = None  # URL to GET the processed PNG (green=match, red=no match). One-time use.


# ----- Crew scanned history (per officer) -----

CrewHistoryDateFilter = Literal["today", "last_7_days", "last_15_days"]


class CrewScannedHistoryItem(BaseModel):
    """One row in the Crew Scanned history list."""

    crew_id: str
    crew_name: str
    boat_id: str
    boat_name: Optional[str] = None
    boat_number: Optional[str] = None
    is_pilot: bool = False
    phone_number: Optional[str] = None
    aadhaar_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    movement_at: Optional[str] = None
    image_url: Optional[str] = None  # Crew face crop URL: /uploads/crew-crops/{crop_id}.png


class CrewScannedHistoryResponse(BaseModel):
    """History response for crew scanned by an officer."""

    date_filter: CrewHistoryDateFilter
    total_records: int
    records: List[CrewScannedHistoryItem]
