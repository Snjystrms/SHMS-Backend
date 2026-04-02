import asyncio
from datetime import timedelta
from typing import Callable, Optional
from secrets import compare_digest
from fastapi import APIRouter, Depends, HTTPException, status, Form
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token
from app.schemas.user import ResendOtpRequest
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


def _send_otp_for_phone(phone: str, get_user_by_phone: Callable[[str], Optional[dict]], not_found_detail: str):
    """Shared: ensure user exists, create/store OTP, send SMS. Raises HTTPException on failure."""
    user = get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    otp, ok = crud_user.create_and_store_otp(phone, settings.SMS_OTP_EXPIRE_MINUTES)
    if not ok or not otp:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate OTP")
    sms = _get_sms()
    if not sms.send_otp(phone, otp):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP")
    return {"masked_mobile": crud_user.mask_mobile(phone), "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES}


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

class LoginRequestForm:
    def __init__(
        self,
        mobile_number: str = Form(None, description="Mobile Number"),
        username: str = Form(None, description="Mobile Number (OAuth2 compatibility)"),
        password: str = Form(...),
        grant_type: str = Form(None, pattern="password"),
        scope: str = Form(""),
        client_id: str = Form(None),
        client_secret: str = Form(None),
    ):
        # Accept either mobile_number or username (for OAuth2 compatibility)
        self.mobile_number = mobile_number or username
        if not self.mobile_number:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either mobile_number or username must be provided"
            )
        self.password = password
        self.grant_type = grant_type
        self.scope = scope
        self.client_id = client_id
        self.client_secret = client_secret

@router.post("/login", response_model=Token)
async def login(form_data: LoginRequestForm = Depends()):
    """Login endpoint - accepts mobile number only."""
    identifier = (form_data.mobile_number or "").strip()
    # Verify the submitted password across every matching password-bearing user.
    # Production data currently contains duplicate active phone numbers across
    # roles, so validating only the first row can produce intermittent 401s.
    candidate_users = crud_user.get_password_login_candidates(identifier)
    if not candidate_users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = None
    verified = False
    for candidate in candidate_users:
        stored_password = candidate.get("password")
        if not stored_password:
            continue
        # Plain-text fallback is still supported for legacy records.
        if not (stored_password.startswith("$2b$") or stored_password.startswith("$2a$")):
            verified = compare_digest(form_data.password, stored_password)
        else:
            verified = await asyncio.to_thread(
                security.verify_password, form_data.password, stored_password
            )
        if verified:
            user = candidate
            break

    if not user or not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Optional: Automatically hash plain text password on first login
    if not user["password"].startswith("$2b$") and not user["password"].startswith("$2a$"):
        hashed = await asyncio.to_thread(
            security.get_password_hash, form_data.password
        )
        crud_user.update_user_password(user["id"], hashed)

    return _token_response(user)


@router.post("/resend-otp")
async def resend_otp(req: ResendOtpRequest):
    """Resend OTP to port officer's mobile."""
    return _send_otp_for_phone(
        req.mobile_number.strip(),
        crud_user.get_officer_by_phone,
        "No port officer found with this mobile number",
    )


## NOTE: /reset-password endpoint removed (use role-specific reset flows).
