"""Port officer endpoints: boat identification by registration number."""
from fastapi import APIRouter, HTTPException, status, Depends
from app.api import deps
from app.core.config import settings
from app.services import user_service, trip_service
from app.schemas.user import BoatIdentifyResponse, PendingBoatRegisterRequest
from app.schemas.trip import BoatTripStatusResponse, BoatMovementCreate, BoatMovementResponse
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

    status_data = trip_service.get_boat_trip_status(boat["id"])
    last_departure = None
    if status_data and status_data.get("departure_details"):
        dep_at = status_data["departure_details"]["departure_at"]
        last_departure = dep_at.strftime("%b %d, %I:%M %p")

    return BoatIdentifyResponse(
        registration_no=boat["boat_number"],
        vessel_name=boat.get("boat_name"),
        owner_name=boat.get("owner_name", ""),
        home_harbor=boat.get("harbor_name"),
        boat_type=boat.get("boat_type"),
        last_logged_departure=last_departure,
        boat_id=boat["id"],
    )


@router.get("/boats/{boat_id}/trip-status", response_model=BoatTripStatusResponse)
async def get_boat_trip_status(
    boat_id: str,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Fetch boat status with respect to trip: docked, sailing, arrived, or partial_arrival.
    Used by the vessel movement UI to show departure details and whether arrival/partial arrival can be logged.
    """
    status_data = trip_service.get_boat_trip_status(boat_id)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boat not found",
        )
    return BoatTripStatusResponse(**status_data)


@router.post(
    "/boats/{boat_id}/movements",
    response_model=BoatMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_boat_movement(
    boat_id: str,
    body: BoatMovementCreate,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Log a boat movement: departure, arrival, or partial arrival.
    - Departure: Can always be logged.
    - Arrival: Requires an open departure record (boat must be sailing).
    - Partial arrival: Required when no departure exists; partial_arrival_reason is required.
      If reason is 'other', partial_arrival_details is required.
    """
    movement, err = trip_service.create_boat_movement(
        boat_id=boat_id,
        movement_type=body.movement_type,
        movement_at=body.movement_at,
        logged_by_user_id=current_user.get("id"),
        partial_arrival_reason=body.partial_arrival_reason,
        partial_arrival_details=body.partial_arrival_details,
    )
    if err:
        if "Boat not found" in err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err,
            )
        if "No departure record found" in err or "partial_arrival_reason" in err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create boat movement",
        )
    return BoatMovementResponse(**movement)


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
