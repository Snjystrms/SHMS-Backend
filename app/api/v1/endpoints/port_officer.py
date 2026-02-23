"""Port officer endpoints: boat identification by registration number."""
from fastapi import APIRouter, HTTPException, status, Depends
from app.api import deps
from app.services import user_service
from app.schemas.user import BoatIdentifyResponse


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
