"""Shared OTP send flow: ensure user exists, create/store OTP, send SMS. Used by auth and boat_owners."""
from typing import Callable, Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.services import user_service as crud_user
from app.utils.sms import get_sms_provider


def get_sms():
    """Return configured SMS provider."""
    return get_sms_provider(
        settings.SMS_PROVIDER,
        twilio_account_sid=settings.TWILIO_ACCOUNT_SID or "",
        twilio_auth_token=settings.TWILIO_AUTH_TOKEN or "",
        twilio_phone=settings.TWILIO_PHONE or "",
        msg91_auth_key=settings.MSG91_AUTH_KEY or "",
        msg91_sender_id=settings.MSG91_SENDER_ID or "",
        fast2sms_api_key=settings.FAST2SMS_API_KEY or "",
    )


def send_otp_for_phone(
    phone: str,
    get_user_by_phone: Callable[[str], Optional[dict]],
    not_found_detail: str,
):
    """
    Ensure user exists, create/store OTP, send SMS.
    Raises HTTPException on failure. Returns dict with masked_mobile and expires_in_minutes.
    """
    user = get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    otp, ok = crud_user.create_and_store_otp(phone, settings.SMS_OTP_EXPIRE_MINUTES)
    if not ok or not otp:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate OTP",
        )
    sms = get_sms()
    if not sms.send_otp(phone, otp):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )
    return {
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }
