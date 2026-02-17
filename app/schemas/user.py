from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str

class UserCreate(UserBase):
    password: Optional[str] = None


class BoatOwnerCreate(BaseModel):
    """Registration for boat owners: name and phone only. OTP is sent after register; they login with OTP."""
    name: str
    phone: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None

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
