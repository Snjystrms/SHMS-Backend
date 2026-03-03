from datetime import timedelta

from fastapi import APIRouter, HTTPException, status

from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token
from app.schemas.user import (
    AgentRegisterRequest,
    AgentVerifyOtpRequest,
    ForgotPasswordRequest,
)
from app.utils.otp_helpers import get_sms, send_otp_for_phone


router = APIRouter()

AGENT_NOT_FOUND_DETAIL = "No agent found with this mobile number"


def _token_response(user: dict):
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
async def register_agent(agent_data: AgentRegisterRequest):
    """
    Step 1 (Agent Registration):

    - Accepts name and mobile number (and optional Aadhaar).
    - Stores a pending registration in temp_users.
    - Sends OTP to the given mobile number.
    - Agent account is created only after OTP verification during login.
    """
    phone = agent_data.phone.strip()
    name = agent_data.name.strip()

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

    existing_agent = crud_user.get_agent_by_phone(phone)
    if existing_agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An agent with this mobile number already exists",
        )

    if not crud_user.create_temp_user(name, phone):
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

    sms = get_sms()
    if not sms.send_otp(phone, otp):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )

    return {
        "success": True,
        "message": "OTP sent to your mobile. Verify to complete agent registration.",
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }


@router.post("/login/send-otp")
async def agent_send_otp(req: ForgotPasswordRequest):
    """
    Step 2a (Existing Agent Login):

    - Accepts mobile_number.
    - Sends an OTP to the agent's mobile (agent must already exist).
    """
    return send_otp_for_phone(
        req.mobile_number.strip(),
        crud_user.get_agent_by_phone,
        AGENT_NOT_FOUND_DETAIL,
    )


@router.post("/login/verify", response_model=Token)
async def agent_verify_otp(req: AgentVerifyOtpRequest):
    """
    Step 2b (OTP Verification for Registration/Login):

    - Verifies OTP for the given mobile number.
    - If a temp_user exists for this phone, creates an 'agent' user and logs them in.
    - If the agent already exists, simply logs them in.
    """
    phone = req.mobile_number.strip()
    if not crud_user.verify_otp(phone, req.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    temp = crud_user.get_temp_user_by_phone(phone)
    if temp:
        role_id = crud_user.get_role_id_by_name("agent")
        if not role_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Agent role not found",
            )

        new_user_dict = {"name": temp["name"], "phone": phone}
        user_id = crud_user.create_user(new_user_dict, role_id)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete agent registration",
            )
        crud_user.delete_temp_user_by_phone(phone)
        user = crud_user.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User data not found",
            )
        return _token_response(user)

    agent = crud_user.get_agent_by_phone(phone)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=AGENT_NOT_FOUND_DETAIL,
        )
    user = crud_user.get_user_by_id(agent["id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User data not found",
        )
    return _token_response(user)

