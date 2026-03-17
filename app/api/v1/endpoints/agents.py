from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.core import security
from app.core.config import settings
from app.api import deps
from app.services import user_service as crud_user
from app.services import trip_service, notification_service
from app.services import bidding_service
from app.services import boat_owner_delivery_service
from app.services import auction_service
from app.services.otp_registration_service import (
    start_temp_user_registration,
    verify_otp_and_login_with_role,
)
from app.schemas.token import Token
from app.schemas.user import (
    AgentRegisterRequest,
    AgentVerifyOtpRequest,
    ForgotPasswordRequest,
)
from app.utils.otp_helpers import get_sms, send_otp_for_phone
from app.schemas.agent_dashboard import AgentDashboardResponse, AgentArrivedBoatItem, AgentDashboardUser
from app.schemas.bidding import (
    BiddingRequestCreate,
    BiddingRequestResponse,
    BiddingRequestItem,
    BiddingRequestListResponse,
)
from app.schemas.boat_owner_delivery import PendingDeliveryItem
from app.schemas.agent_auction import AgentAuctionListItem


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

    return start_temp_user_registration(
        name=name,
        phone=phone,
        duplicate_check=crud_user.get_agent_by_phone,
        duplicate_error_detail="An agent with this mobile number already exists",
        success_message="OTP sent to your mobile. Verify to complete agent registration.",
    )


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
    user = verify_otp_and_login_with_role(
        phone=phone,
        otp=req.otp,
        role_name="agent",
        get_user_by_phone=crud_user.get_agent_by_phone,
    )
    return _token_response(user)


@router.get("/dashboard", response_model=AgentDashboardResponse)
async def get_agent_dashboard(
    current_user: dict = Depends(deps.get_agent_user),
):
    data = trip_service.get_agent_dashboard_arrivals(agent_id=current_user["id"])
    arrived_boats = [AgentArrivedBoatItem(**b) for b in (data.get("arrived_boats") or [])]
    return AgentDashboardResponse(
        user=AgentDashboardUser(
            id=current_user.get("id", ""),
            name=current_user.get("name", ""),
            phone=current_user.get("phone") or "",
            email=current_user.get("email") or "",
        ),
        arrived_boats_count=int(data.get("arrived_boats_count") or 0),
        arrived_boats=arrived_boats,
    )


@router.post(
    "/bidding-request",
    response_model=BiddingRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_bidding_request(
    body: BiddingRequestCreate,
    current_user: dict = Depends(deps.get_agent_user),
):
    """
    Agent sends a bidding request for an arrived boat.
    The request is stored as 'pending' and a notification is sent to the boat owner.
    """
    result, err = bidding_service.create_bidding_request(
        boat_id=body.boat_id,
        agent_id=current_user["id"],
        note=body.note,
    )
    if err:
        if "not found" in err.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err)
        if "already have a pending" in err.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    boat_label = result.get("boat_number") or result.get("boat_name") or body.boat_id
    agent_name = result.get("agent_name") or "An agent"

    notification_service.create_notification(
        notification_type="bidding_request",
        title=f"New bidding request for {boat_label}",
        message=f"{agent_name} has requested to bid on boat {boat_label}.",
        metadata={
            "bidding_request_id": result["id"],
            "boat_id": body.boat_id,
            "boat_number": result.get("boat_number"),
            "boat_name": result.get("boat_name"),
            "agent_id": current_user["id"],
            "agent_name": agent_name,
        },
        recipient_role="boat_owner",
        priority="medium",
    )

    return BiddingRequestResponse(
        success=True,
        message="Bidding request sent to boat owner",
        bidding_request=BiddingRequestItem(**{k: v for k, v in result.items() if k != "boat_owner_id"}),
    )


@router.get("/bidding-requests", response_model=BiddingRequestListResponse)
async def list_my_bidding_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(deps.get_agent_user),
):
    """List all bidding requests sent by the current agent."""
    requests = bidding_service.list_bidding_requests_for_agent(
        agent_id=current_user["id"],
        status_filter=status_filter,
    )
    return BiddingRequestListResponse(
        success=True,
        total=len(requests),
        bidding_requests=[BiddingRequestItem(**r) for r in requests],
    )


@router.get(
    "/deliveries",
    response_model=list[PendingDeliveryItem],
)
async def list_agent_deliveries(
    status_filter: Optional[str] = Query("pending", alias="status"),
    current_user: dict = Depends(deps.get_agent_user),
):
    """
    List deliveries for the authenticated agent filtered by status.
    Query param: ?status=pending|completed
    """
    status_value = (status_filter or "pending").strip().lower()
    if status_value not in {"pending", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Allowed values: pending, completed",
        )

    items = boat_owner_delivery_service.get_deliveries_for_agent(
        agent_id=current_user["id"],
        status_filter=status_value,
    )
    return items


@router.get(
    "/auctions",
    response_model=list[AgentAuctionListItem],
)
async def list_agent_auctions(
    status_filter: Optional[str] = Query("active", alias="status"),
    current_user: dict = Depends(deps.get_agent_user),
):
    """
    Agent auctions list for app tabs.
    Query param: ?status=active|completed
    """
    status_value = (status_filter or "active").strip().lower()
    if status_value not in {"active", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Allowed values: active, completed",
        )
    return auction_service.list_agent_auction_cards(
        agent_id=current_user["id"],
        status=status_value,
    )

