from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from app.services import user_service as crud_user, notification_service, trip_service
from app.schemas.user import UserCreate, UserUpdate, BoatUpdate
from app.api import deps
from app.schemas.trip import BoatTripStatusResponse
from app.core import security
from app.schemas.crew import (
    CrewScannedHistoryResponse,
    CrewScannedHistoryItem,
    CrewHistoryDateFilter,
)
from app.schemas.agent_auction import AgentAuctionListItem
from app.schemas.admin_buyers import AdminBuyerListItem, AdminBuyerListResponse
from app.schemas.buyer_delivery import DeliveryListItem
from app.services import admin_delivery_service

router = APIRouter()

PAGE_MIN_DETAIL = "page must be >= 1"
PAGE_SIZE_MIN_DETAIL = "page_size must be >= 1"

# ==================== Dashboard ====================

@router.get("/dashboard")
async def admin_dashboard(
    current_admin: dict = Depends(deps.get_admin_user),
):
    """Admin dashboard: quick snapshot counts for non-admin roles."""
    data = crud_user.get_admin_dashboard_role_counts()
    counts = data.get("counts") or {}
    return {
        "success": True,
        "user": {
            "id": current_admin.get("id", ""),
            "name": current_admin.get("name", ""),
        },
        "quick_snapshot": {
            "boat_owners": int(counts.get("boat_owner") or 0),
            "harbour_officers": int(counts.get("officer") or 0),
            "agents": int(counts.get("agent") or 0),
            "buyers": int(counts.get("buyer") or 0),
        },
        "updated_at": data.get("updated_at"),
    }


# ==================== Notifications ====================

@router.get("/notifications")
async def list_notifications(
    limit: Optional[int] = 50,
    unread_only: bool = False,
    current_admin: dict = Depends(deps.get_admin_user),
):
    """List notifications for admin (e.g. boat not registered alerts)."""
    notifications = notification_service.list_admin_notifications(
        limit=limit or 50,
        unread_only=unread_only,
    )
    return {"success": True, "notifications": notifications}


@router.get("/agents")
async def list_agents(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    current_admin: dict = Depends(deps.get_admin_user),
):
    """
    Admin-only: List agents with pagination and optional search by name/phone.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=PAGE_MIN_DETAIL,
        )
    if page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=PAGE_SIZE_MIN_DETAIL,
        )
    if page_size > 200:
        page_size = 200

    offset = (page - 1) * page_size
    agents, total = crud_user.get_agents_paginated(
        search=search,
        limit=page_size,
        offset=offset,
    )
    return {
        "success": True,
        "page": page,
        "page_size": page_size,
        "total": total,
        "agents": agents,
    }


@router.get("/buyers", response_model=AdminBuyerListResponse)
async def list_buyers(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    current_admin: dict = Depends(deps.get_admin_user),
):
    """
    Admin-only: List buyers with pagination and optional search by name/phone.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=PAGE_MIN_DETAIL,
        )
    if page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=PAGE_SIZE_MIN_DETAIL,
        )
    if page_size > 200:
        page_size = 200

    offset = (page - 1) * page_size
    buyers, total = crud_user.get_buyers_paginated(
        search=search,
        limit=page_size,
        offset=offset,
    )
    return AdminBuyerListResponse(
        success=True,
        page=page,
        page_size=page_size,
        total=total,
        buyers=[AdminBuyerListItem(**b) for b in buyers],
    )


@router.get(
    "/buyers/{buyer_id}/deliveries",
    response_model=list[DeliveryListItem],
)
async def list_deliveries_for_buyer_admin(
    buyer_id: str,
    status_filter: Optional[str] = Query("pending", alias="status"),
    current_admin: dict = Depends(deps.get_admin_user),
):
    """
    Admin-only: list deliveries for a buyer filtered by delivery status.
    Query param: ?status=pending|completed
    """
    status_value = (status_filter or "pending").strip().lower()
    if status_value not in {"pending", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Allowed values: pending, completed",
        )

    deliveries = admin_delivery_service.list_buyer_deliveries_for_admin(
        buyer_id=buyer_id,
        status_filter=status_value,
    )
    return [DeliveryListItem(**d) for d in deliveries]



@router.post("/officers", status_code=status.HTTP_201_CREATED)
async def create_officer_account(
    user_data: UserCreate,
    current_admin: dict = Depends(deps.get_admin_user)
):
    """Admin-only endpoint to create an officer account."""
    # Check if user already exists
    existing_user = crud_user.get_user_by_identifier(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Get officer role ID
    role_id = crud_user.get_role_id_by_name("officer")
    if not role_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Officer role not found in database"
        )
    
    # Hash password
    hashed_password = security.get_password_hash(user_data.password)
    
    # Create user
    new_user_dict = user_data.dict()
    new_user_dict["password"] = hashed_password
    
    user_id = crud_user.create_officer_user(new_user_dict, role_id)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create officer account"
        )
    
    return {
        "success": True,
        "user_id": user_id,
        "message": "Officer account created successfully"
    }

@router.get("/officers")
async def list_officers(current_admin: dict = Depends(deps.get_admin_user)):
    """List all port officers."""
    officers = crud_user.get_officers()
    return {"success": True, "officers": officers}

@router.get("/officers/{officer_id}")
async def get_officer(officer_id: str, current_admin: dict = Depends(deps.get_admin_user)):
    """Get details of a specific officer."""
    officer = crud_user.get_user_by_id(officer_id)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    return {"success": True, "officer": officer}

@router.put("/officers/{officer_id}")
async def update_officer(
    officer_id: str,
    user_data: UserUpdate,
    current_admin: dict = Depends(deps.get_admin_user)
):
    """Update an officer's details."""
    # Check if officer exists
    existing_officer = crud_user.get_user_by_id(officer_id)
    if not existing_officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    
    # If password is being updated, hash it
    update_dict = user_data.dict(exclude_unset=True)
    if "password" in update_dict and update_dict["password"]:
        update_dict["password"] = security.get_password_hash(update_dict["password"])
    
    result = crud_user.update_user(officer_id, update_dict)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update officer"
        )
    
    return {"success": True, "message": "Officer updated successfully"}

@router.delete("/officers/{officer_id}")
async def delete_officer(officer_id: str, current_admin: dict = Depends(deps.get_admin_user)):
    """Soft delete an officer account."""
    # Check if officer exists
    existing_officer = crud_user.get_user_by_id(officer_id)
    if not existing_officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found"
        )
    
    result = crud_user.delete_user(officer_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete officer"
        )
    
    return {"success": True, "message": "Officer deleted successfully"}

# ==================== Boat Owner CRUD Operations ====================

@router.get("/boat-owners")
async def list_boat_owners(current_admin: dict = Depends(deps.get_admin_user)):
    """List all boat owners."""
    boat_owners = crud_user.get_boat_owners()
    return {"success": True, "boat_owners": boat_owners}

@router.get("/boat-owners/{boat_owner_id}")
async def get_boat_owner(boat_owner_id: str, current_admin: dict = Depends(deps.get_admin_user)):
    """Get details of a specific boat owner."""
    boat_owner = crud_user.get_user_by_id(boat_owner_id)
    if not boat_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boat owner not found"
        )
    return {"success": True, "boat_owner": boat_owner}

@router.put("/boat-owners/{boat_owner_id}")
async def update_boat_owner(
    boat_owner_id: str,
    user_data: UserUpdate,
    current_admin: dict = Depends(deps.get_admin_user)
):
    """Update a boat owner's details."""
    # Check if boat owner exists
    existing_boat_owner = crud_user.get_user_by_id(boat_owner_id)
    if not existing_boat_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boat owner not found"
        )
    
    # If password is being updated, hash it
    update_dict = user_data.dict(exclude_unset=True)
    if "password" in update_dict and update_dict["password"]:
        update_dict["password"] = security.get_password_hash(update_dict["password"])
    
    result = crud_user.update_user(boat_owner_id, update_dict)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update boat owner"
        )
    
    return {"success": True, "message": "Boat owner updated successfully"}

@router.delete("/boat-owners/{boat_owner_id}")
async def delete_boat_owner(boat_owner_id: str, current_admin: dict = Depends(deps.get_admin_user)):
    """Soft delete a boat owner account."""
    # Check if boat owner exists
    existing_boat_owner = crud_user.get_user_by_id(boat_owner_id)
    if not existing_boat_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boat owner not found"
        )
    
    result = crud_user.delete_user(boat_owner_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete boat owner"
        )
    
    return {"success": True, "message": "Boat owner deleted successfully"}


# ==================== Boat CRUD (admin) ====================

@router.get("/boats")
async def list_boats(
    boat_owner_id: Optional[str] = None,
    current_admin: dict = Depends(deps.get_admin_user),
):
    """List all boats. Optionally filter by boat_owner_id."""
    boats = crud_user.get_all_boats(boat_owner_id=boat_owner_id)
    # Enrich each boat with latest movement id and status
    for boat in boats:
        status_data = trip_service.get_boat_trip_status(boat["id"])
        trip_status = status_data["trip_status"] if status_data else "docked"
        boat["boat_status"] = "At sea" if trip_status == "sailing" else "At harbour"
        boat["latest_movement_id"] = status_data.get("latest_movement_id") if status_data else None
        boat["latest_movement_status"] = status_data.get("movement_type") if status_data else None
    return {"success": True, "boats": boats}


@router.get("/boats/{boat_id}")
async def get_boat(boat_id: str, current_admin: dict = Depends(deps.get_admin_user)):
    """Get a boat by id."""
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    return {"success": True, "boat": boat}


@router.get("/boats/{boat_id}/details")
async def get_boat_details(
    boat_id: str,
    request: Request,
    current_admin: dict = Depends(deps.get_admin_user),
):
    """
    Admin API: aggregate boat details for Boat Details screen:
    - basic boat info
    - current trip (if any)
    - last 3 trips
    - last 3 auctions
    - list of issues (placeholder)
    """
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boat not found",
        )

    status_data = trip_service.get_boat_trip_status(boat_id)
    current_trip = None
    if status_data:
        base_url = str(request.base_url).rstrip("/")
        if (
            status_data.get("departure_details")
            and status_data["departure_details"].get("image_url")
        ):
            img = status_data["departure_details"]["image_url"]
            if img and not img.startswith("http"):
                status_data["departure_details"]["image_url"] = (
                    f"{base_url}/{img.lstrip('/')}"
                )
        if status_data.get("last_movement_image_url"):
            img = status_data["last_movement_image_url"]
            if img and not img.startswith("http"):
                status_data["last_movement_image_url"] = (
                    f"{base_url}/{img.lstrip('/')}"
                )

        trip_resp = BoatTripStatusResponse(**status_data)
        dep = trip_resp.departure_details
        current_trip = {
            "trip_status": trip_resp.trip_status,
            "movement_type": trip_resp.movement_type,
            "departure_at": dep.departure_at if dep else None,
            "from_port": dep.from_port if dep else None,
            "vessel_type": dep.vessel_type if dep else boat.get("boat_type"),
            "crew_count": dep.crew_count if dep else None,
            "status_label": dep.status_label if dep else None,
            "image_url": dep.image_url if dep else None,
        }

    last_trips = trip_service.get_last_trips_for_boat(boat_id, limit=3)

    from app.services import auction_service

    last_auctions = auction_service.get_last_auctions_for_boat(boat_id, limit=3)

    issues: list[dict] = []

    return {
        "success": True,
        "boat": boat,
        "current_trip": current_trip,
        "last_trips": last_trips,
        "last_auctions": last_auctions,
        "issues": issues,
    }


@router.get(
    "/officers/{officer_id}/crew-history",
    response_model=CrewScannedHistoryResponse,
)
async def get_officer_crew_history(
    officer_id: str,
    date_filter: CrewHistoryDateFilter = "today",
    is_register: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
    current_admin: dict = Depends(deps.get_admin_user),
):
    """
    Admin API: list crew members registered by a specific officer.

    Supports filtering by registration status (`is_register`) and basic
    page/page_size pagination.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be >= 1",
        )
    if page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_size must be >= 1",
        )
    if page_size > 200:
        page_size = 200

    offset = (page - 1) * page_size

    records_raw = trip_service.get_registered_crew_history(
        officer_user_id=officer_id,
        date_filter=date_filter,
        is_register=is_register,
        offset=offset,
        limit=page_size,
    )
    records = [CrewScannedHistoryItem(**r) for r in records_raw]
    return CrewScannedHistoryResponse(
        date_filter=date_filter,
        total_records=len(records),
        records=records,
    )


@router.get(
    "/agents/{agent_id}/auctions",
    response_model=List[AgentAuctionListItem],
)
async def list_auctions_for_agent_admin(
    agent_id: str,
    status_filter: Optional[str] = Query("pending", alias="status"),
    current_admin: dict = Depends(deps.get_admin_user),
):
    """
    Admin: list auctions created by a specific agent.

    Query param: ?status=pending|completed
    - pending => scheduled + active
    - completed => completed
    """
    status_value = (status_filter or "pending").strip().lower()
    if status_value not in {"pending", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Allowed values: pending, completed",
        )

    from app.services import auction_service

    return auction_service.list_agent_auction_cards_for_admin(
        agent_id=agent_id,
        status=status_value,
    )


@router.put("/boats/{boat_id}")
async def update_boat(
    boat_id: str,
    data: BoatUpdate,
    current_admin: dict = Depends(deps.get_admin_user),
):
    """Update a boat."""
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    ok = crud_user.update_boat(boat_id, data.dict(exclude_unset=True))
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update boat")
    return {"success": True, "boat": crud_user.get_boat_by_id(boat_id)}


@router.delete("/boats/{boat_id}")
async def delete_boat(boat_id: str, current_admin: dict = Depends(deps.get_admin_user)):
    """Soft delete a boat."""
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    ok = crud_user.delete_boat(boat_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete boat")
    return {"success": True, "message": "Boat deleted"}

