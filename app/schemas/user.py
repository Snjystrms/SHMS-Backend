from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str

class UserCreate(UserBase):
    password: Optional[str] = None
    aadhaar_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None


class BoatOwnerCreate(BaseModel):
    """Registration for boat owners: name and phone only. OTP is sent after register; they login with OTP."""
    name: str
    phone: str


class AgentRegisterRequest(BaseModel):
    """Registration for agents: name and mobile number (OTP-based login)."""
    name: str
    phone: str
    aadhaar_number: Optional[str] = None


class AgentVerifyOtpRequest(BaseModel):
    """Request body for agent OTP verification (login / complete registration)."""
    mobile_number: str
    otp: str


class BuyerRegisterRequest(BaseModel):
    """Registration for buyers: name and mobile number (OTP-based login)."""
    name: str
    phone: str


class BuyerVerifyOtpRequest(BaseModel):
    """Request body for buyer OTP verification (login / complete registration)."""
    mobile_number: str
    otp: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    aadhaar_number: Optional[str] = None
    emergency_contact_number: Optional[str] = None

class User(UserBase):
    id: str
    role_id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    mobile_number: str
    password: str


class ForgotPasswordRequest(BaseModel):
    """Request with mobile number. Used for forgot-password and OTP send/resend."""
    mobile_number: str


# Same shape as ForgotPasswordRequest; kept for API clarity (resend-otp).
ResendOtpRequest = ForgotPasswordRequest


class ResetPasswordRequest(BaseModel):
    mobile_number: str
    otp: str
    new_password: str
    confirm_password: str


class BoatOwnerVerifyOtpRequest(BaseModel):
    """Request body for boat owner OTP verification (login)."""
    mobile_number: str
    otp: str


# ----- Boat (owned by boat_owner) -----
class BoatCreate(BaseModel):
    boat_name: str
    boat_type: str
    boat_number: str
    harbor_name: Optional[str] = "mumbai"
    boat_document: Optional[str] = None
    boat_document_content_type: Optional[str] = None
    boat_document_filename: Optional[str] = None


class BoatUpdate(BaseModel):
    boat_name: Optional[str] = None
    boat_type: Optional[str] = None
    boat_number: Optional[str] = None
    harbor_name: Optional[str] = None
    boat_document: Optional[str] = None
    boat_document_content_type: Optional[str] = None
    boat_document_filename: Optional[str] = None


# ----- Port officer boat identification -----
class PendingBoatRegisterRequest(BaseModel):
    """Request to register a pending boat when identification fails. Sends SMS to owner."""
    boat_number: str
    mobile_number: str


class BoatIdentifyResponse(BaseModel):
    """Boat details returned after identification (matches Scan Boat UI)."""
    registration_no: str
    vessel_name: Optional[str] = None
    owner_name: str
    home_harbor: Optional[str] = None
    boat_type: Optional[str] = None
    last_logged_departure: Optional[str] = None  # e.g. "3 days ago" when departure tracking exists
    boat_id: str
