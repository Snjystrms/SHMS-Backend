"""Boat owner registration and OTP login. Separate from main auth (officer/admin)."""
from datetime import timedelta
from fastapi import APIRouter, HTTPException, status
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token
from app.schemas.user import BoatOwnerCreate, ForgotPasswordRequest, BoatOwnerVerifyOtpRequest
from app.utils.sms import get_sms_provider

router = APIRouter()


def _get_sms():
    return get_sms_provider(
        settings.SMS_PROVIDER,
        twilio_account_sid=settings.TWILIO_ACCOUNT_SID or "",
        twilio_auth_token=settings.TWILIO_AUTH_TOKEN or "",
        twilio_phone=settings.TWILIO_PHONE or "",
        msg91_auth_key=settings.MSG91_AUTH_KEY or "",
        msg91_sender_id=settings.MSG91_SENDER_ID or "",
        fast2sms_api_key=settings.FAST2SMS_API_KEY or "",
    )


def _token_response(user: dict):
    """Build Token response from user dict (id, name, email, role)."""
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user["id"],
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user.get("email") or "",
            "role": user["role"],
        },
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_boat_owner(user_data: BoatOwnerCreate):
    """
    Save boat owner to temp_users and send OTP. User is created in users only after OTP verify.
    """
    phone = user_data.phone.strip()
    existing_boat_owner = crud_user.get_boat_owner_by_phone(phone)
    if existing_boat_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A boat owner with this mobile number already exists",
        )
    if not crud_user.create_temp_user(user_data.name, phone):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save registration",
        )
    otp, ok = crud_user.create_and_store_otp(phone, settings.SMS_OTP_EXPIRE_MINUTES)
    if not ok or not otp:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate OTP",
        )
    sms = _get_sms()
    if not sms.send_otp(phone, otp):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )
    return {
        "success": True,
        "message": "OTP sent to your mobile. Verify to complete registration.",
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }


@router.post("/login/send-otp")
async def boat_owner_send_otp(req: ForgotPasswordRequest):
    """Send OTP to boat owner's mobile for login. Boat owner must already exist."""
    phone = req.mobile_number.strip()
    owner = crud_user.get_boat_owner_by_phone(phone)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No boat owner found with this mobile number",
        )
    otp, ok = crud_user.create_and_store_otp(phone, settings.SMS_OTP_EXPIRE_MINUTES)
    if not ok or not otp:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate OTP",
        )
    sms = _get_sms()
    if not sms.send_otp(phone, otp):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )
    return {
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }


@router.post("/login/resend-otp")
async def boat_owner_resend_otp(req: ForgotPasswordRequest):
    """Resend OTP to boat owner's mobile."""
    return await boat_owner_send_otp(req)


@router.post("/login/verify", response_model=Token)
async def boat_owner_verify_otp(req: BoatOwnerVerifyOtpRequest):
    """Verify OTP: if temp_user exists, create user then return token; else login existing boat owner."""
    phone = req.mobile_number.strip()
    if not crud_user.verify_otp(phone, req.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    temp = crud_user.get_temp_user_by_phone(phone)
    if temp:
        role_id = crud_user.get_role_id_by_name("boat_owner")
        if not role_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Boat owner role not found",
            )
        new_user_dict = {"name": temp["name"], "phone": phone}
        user_id = crud_user.create_user(new_user_dict, role_id)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete registration",
            )
        crud_user.delete_temp_user_by_phone(phone)
        user = crud_user.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User data not found")
        return _token_response(user)
    owner = crud_user.get_boat_owner_by_phone(phone)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No boat owner found with this mobile number",
        )
    user = crud_user.get_user_by_id(owner["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User data not found")
    return _token_response(user)
