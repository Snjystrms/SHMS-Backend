from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.services.otp_registration_service import (
    start_temp_user_registration,
    verify_otp_and_login_with_role,
)
from app.schemas.token import Token
from app.schemas.user import (
    BuyerRegisterRequest,
    BuyerVerifyOtpRequest,
    ForgotPasswordRequest,
)
from app.utils.otp_helpers import send_otp_for_phone
from app.services import buyer_dashboard_service
from app.schemas.buyer_dashboard import (
    BuyerDashboardResponse,
    BuyerDashboardUser,
    LiveAuctionItem,
)


router = APIRouter()

BUYER_NOT_FOUND_DETAIL = "No buyer found with this mobile number"


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


@router.get("/dashboard", response_model=BuyerDashboardResponse)
async def get_buyer_dashboard(
    current_user: dict = Depends(deps.get_buyer_user),
):
    """Buyer dashboard: summary stats and live auctions with my bid."""
    data = buyer_dashboard_service.get_buyer_dashboard(buyer_id=current_user["id"])
    live_auctions = [LiveAuctionItem(**item) for item in data.get("live_auctions", [])]
    return BuyerDashboardResponse(
        user=BuyerDashboardUser(
            id=str(current_user.get("id", "")),
            name=str(current_user.get("name", "")),
        ),
        total_bids=data.get("total_bids", 0),
        pending_delivery=data.get("pending_delivery", 0),
        live_auctions=live_auctions,
        updated_at=data.get("updated_at"),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_buyer(buyer_data: BuyerRegisterRequest):
    """
    Buyer Registration:
    - Accepts name, mobile number, and optional Aadhaar.
    - Stores a pending registration in temp_users.
    - Sends OTP to the mobile number.
    - Buyer user is created after OTP verification during login.
    """
    phone = buyer_data.phone.strip()
    name = buyer_data.name.strip()
    aadhaar = (buyer_data.aadhaar_number or "").strip() or None

    return start_temp_user_registration(
        name=name,
        phone=phone,
        duplicate_check=crud_user.get_buyer_by_phone,
        duplicate_error_detail="A buyer with this mobile number already exists",
        success_message="OTP sent to your mobile. Verify to complete buyer registration.",
        aadhaar_number=aadhaar,
    )


@router.post("/login/send-otp")
async def buyer_send_otp(req: ForgotPasswordRequest):
    """Send OTP to buyer's mobile for login. Buyer must already exist."""
    return send_otp_for_phone(
        req.mobile_number.strip(),
        crud_user.get_buyer_by_phone,
        BUYER_NOT_FOUND_DETAIL,
    )


@router.post("/login/verify", response_model=Token)
async def buyer_verify_otp(req: BuyerVerifyOtpRequest):
    """
    Buyer OTP verification:
    - Verifies OTP.
    - If temp_user exists, creates a 'buyer' user and logs them in.
    - Else logs in existing buyer.
    """
    phone = req.mobile_number.strip()
    user = verify_otp_and_login_with_role(
        phone=phone,
        otp=req.otp,
        role_name="buyer",
        get_user_by_phone=crud_user.get_buyer_by_phone,
    )
    return _token_response(user)

