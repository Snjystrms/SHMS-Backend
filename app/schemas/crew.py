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
    email: Optional[str] = None
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


class CrewMemberScanResponse(BaseModel):
    """Minimal crew fields exposed in group scan responses."""
    id: str
    name: str


class CrewFaceScanResult(BaseModel):
    """One detected face and its match (if any)."""
    det_score: float
    distance: Optional[float] = None
    is_match: bool
    crew_member: Optional[CrewMemberScanResponse] = None
    crop_id: Optional[str] = None  # UUID for crew face crop; use when attaching crew to movement for image_url in history.


class CrewGroupScanResponse(BaseModel):
    """Response for group photo scan (crew identification)."""
    faces: List[CrewFaceScanResult]


# ----- Crew scanned history (per officer) -----

CrewHistoryDateFilter = Literal["today", "last_7_days", "last_15_days"]


class CrewScannedHistoryItem(BaseModel):
    """
    One row in the Crew history list shown to a port officer.

    This is intentionally slimmed down to only expose the fields used in the
    mobile UI: name, registration status, phone, emergency contact, aadhaar
    and a timestamp for ordering/labeling.
    """

    crew_id: str
    crew_name: str
    phone_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    aadhaar_number: Optional[str] = None
    is_register: bool = False
    movement_at: Optional[str] = None
    image_url: Optional[str] = None


class CrewScannedHistoryResponse(BaseModel):
    """History response for crew scanned by an officer."""

    date_filter: CrewHistoryDateFilter
    total_records: int
    records: List[CrewScannedHistoryItem]
