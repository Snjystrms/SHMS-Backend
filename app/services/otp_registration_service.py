"""Shared helpers for OTP-based registration and login for simple phone-based roles.

Used by boat owners, agents, buyers, etc. Keeps endpoints thin and avoids duplication.
"""
from typing import Callable, Dict, Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.services import user_service as crud_user
from app.utils.otp_helpers import get_sms


def start_temp_user_registration(
    *,
    name: str,
    phone: str,
    duplicate_check: Callable[[str], Optional[Dict]],
    duplicate_error_detail: str,
    success_message: str,
) -> Dict:
    """Create/overwrite temp_users row and send OTP to phone."""
    phone = phone.strip()
    name = name.strip()

    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mobile number is required",
        )
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required",
        )

    existing = duplicate_check(phone)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=duplicate_error_detail,
        )

    if not crud_user.create_temp_user(name, phone):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save registration",
        )

    otp, ok = crud_user.create_and_store_otp(
        phone, settings.SMS_OTP_EXPIRE_MINUTES
    )
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
        "success": True,
        "message": success_message,
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }


def verify_otp_and_login_with_role(
    *,
    phone: str,
    otp: str,
    role_name: str,
    get_user_by_phone: Callable[[str], Optional[Dict]],
) -> Dict:
    """
    Shared flow:
    - Verify OTP for phone.
    - If temp_user exists: create user with given role, delete temp user, return user dict.
    - Else: look up existing user for this role by phone and return user dict.
    """
    phone = phone.strip()
    if not crud_user.verify_otp(phone, otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    temp = crud_user.get_temp_user_by_phone(phone)
    if temp:
        role_id = crud_user.get_role_id_by_name(role_name)
        if not role_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{role_name.replace('_', ' ').title()} role not found",
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User data not found",
            )
        return user

    existing = get_user_by_phone(phone)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {role_name.replace('_', ' ')} found with this mobile number",
        )
    user = crud_user.get_user_by_id(existing["id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User data not found",
        )
    return user

