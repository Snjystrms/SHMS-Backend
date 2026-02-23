"""Port officer endpoints: boat identification by registration number."""
from fastapi import APIRouter, HTTPException, status, Depends
from app.api import deps
from app.core.config import settings
from app.services import user_service
from app.schemas.user import BoatIdentifyResponse, PendingBoatRegisterRequest
from app.utils.sms import get_sms_provider


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


router = APIRouter()


@router.post("/boats/identify/{boat_number}", response_model=BoatIdentifyResponse)
async def identify_boat(
    boat_number: str,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Port officer looks up a boat by registration/boat number.
    Returns boat details (registration, vessel name, owner, harbor, type).
    """
    boat_number = (boat_number or "").strip()
    if not boat_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Boat number is required",
        )

    boat = user_service.get_boat_by_number_with_owner(boat_number)
    if not boat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boat not found",
        )

    return BoatIdentifyResponse(
        registration_no=boat["boat_number"],
        vessel_name=boat.get("boat_name"),
        owner_name=boat.get("owner_name", ""),
        home_harbor=boat.get("harbor_name"),
        boat_type=boat.get("boat_type"),
        last_logged_departure=None,  # Populated when departure tracking is implemented
        boat_id=boat["id"],
    )


@router.post("/boats/pending-register", status_code=status.HTTP_201_CREATED)
async def register_pending_boat(
    body: PendingBoatRegisterRequest,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    When boat identification fails, port officer adds boat number + owner mobile.
    Creates boat with is_register=false and sends SMS: "This boat is not registered. Please register."
    """
    boat_number = (body.boat_number or "").strip()
    mobile_number = (body.mobile_number or "").strip()
    if not boat_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Boat number is required",
        )
    if not mobile_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mobile number is required",
        )

    boat_id = user_service.create_pending_boat(boat_number, mobile_number)
    if not boat_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create pending boat",
        )

    sms = _get_sms()
    message = "This boat is not registered. Please register."
    sms.send_message(mobile_number, message)

    return {
        "success": True,
        "boat_id": boat_id,
        "boat_number": boat_number,
        "message": "Pending boat created. SMS sent to owner.",
    }
