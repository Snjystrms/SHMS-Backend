"""Boat owner registration, OTP login, and boat CRUD (own boats only)."""
import json
from datetime import date, timedelta
from typing import Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, status, UploadFile
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user, notification_service
from app.services import bidding_service
from app.services import auction_service
from app.services import boat_owner_sales_service
from app.services.otp_registration_service import (
    start_temp_user_registration,
    verify_otp_and_login_with_role,
)
from app.schemas.token import Token
from app.schemas.auction import Auction
from app.schemas.user import BoatOwnerCreate, BoatCreate, BoatUpdate, ForgotPasswordRequest, BoatOwnerVerifyOtpRequest
from app.schemas.bidding import (
    BiddingRequestAction,
    BiddingRequestItem,
    BiddingRequestListResponse,
    BiddingRequestResponse,
)
from app.api import deps
from app.utils.otp_helpers import get_sms, send_otp_for_phone
from app.utils.uploads import ALLOWED_BOAT_DOCUMENT_TYPES, save_boat_document
from app.services import trip_service
from app.services import boat_owner_delivery_service
from app.schemas.boat_owner_delivery import (
    ScanDeliveryRequest,
    ScanDeliveryResponse,
    InitiateDeliveryResponse,
    RecordDeliveryRequest,
    RecordDeliveryResponse,
    PendingDeliveryItem,
)
from app.schemas.trip import (
    TripDetailsAtSeaResponse,
    TripDetailsAtHarbourResponse,
    TripDetailsInventoryItem,
    TripDetailsCrewMember,
    TripDetailsDeparture,
    TripDetailsArrival,
)
from app.schemas.boat_owner_sales import BoatOwnerSalesReportResponse, SalesReportFilter

router = APIRouter()

BOAT_OWNER_NOT_FOUND_DETAIL = "No boat owner found with this mobile number"


@router.get("/dashboard")
async def boat_owner_dashboard(
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Boat owner dashboard: quick activity counts, pending auction boats."""
    data = trip_service.get_boat_owner_dashboard(current_user["id"])
    return {
        "success": True,
        "user": {
            "id": current_user["id"],
            "name": current_user["name"],
        },
        "quick_activity": data["quick_activity"],
        "pending_auctions": data["pending_auctions"],
        "updated_at": data["updated_at"],
    }


@router.get(
    "/auctions",
    response_model=list[Auction],
)
async def list_my_auctions(
    current_user: dict = Depends(deps.get_boat_owner_or_agent_user),
):
    """
    List auctions for the authenticated boat owner or agent.

    Includes:
    - Auctions created directly by the boat owner (movement-based).
    - Auctions created by an agent using an approved bidding request where this
      boat owner is the seller (seller_id stored as boat_owner_id).
    """
    if current_user.get("role") == "agent":
        auctions = auction_service.list_auctions_for_agent(current_user["id"])
    else:
        auctions = auction_service.list_auctions_for_seller(current_user["id"])
    return auctions


@router.get("/notifications")
async def list_my_notifications(
    limit: int = 50,
    unread_only: bool = False,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """
    List notifications for the authenticated boat owner.
    Returns only notifications whose metadata.boat_owner_id matches the current user.
    """
    notifications = notification_service.list_boat_owner_notifications(
        boat_owner_id=current_user["id"],
        limit=limit or 50,
        unread_only=unread_only,
    )
    return {"success": True, "notifications": notifications}


@router.get("/sales/report", response_model=BoatOwnerSalesReportResponse)
async def boat_owner_sales_report(
    filter: SalesReportFilter = Query("last_three_months"),
    from_date: Optional[date] = Query(None, alias="from_date"),
    to_date: Optional[date] = Query(None, alias="to_date"),
    search: Optional[str] = Query(None, alias="search"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """
    Boat owner sales report (per-auction rows).

    - Earnings are computed from `auctions.sale` (set when delivery is recorded).
    - Date filtering applies to auction `start_time`.
    """
    try:
        return boat_owner_sales_service.get_sales_report(
            boat_owner_id=current_user["id"],
            filter_name=filter,
            from_date=from_date,
            to_date=to_date,
            search=search,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_boat_owner(user_data: BoatOwnerCreate):
    """
    Save boat owner to temp_users and send OTP. User is created in users only after OTP verify.
    """
    phone = user_data.phone.strip()
    name = user_data.name.strip()

    # Preserve existing name uniqueness check for boat owners
    existing_by_name = crud_user.get_boat_owner_by_name(name)
    if existing_by_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A boat owner with this name already exists",
        )

    return start_temp_user_registration(
        name=name,
        phone=phone,
        duplicate_check=crud_user.get_boat_owner_by_phone,
        duplicate_error_detail="A boat owner with this mobile number already exists",
        success_message="OTP sent to your mobile. Verify to complete registration.",
    )


@router.post("/login/send-otp")
async def boat_owner_send_otp(req: ForgotPasswordRequest):
    """Send OTP to boat owner's mobile for login. Boat owner must already exist."""
    return send_otp_for_phone(
        req.mobile_number.strip(),
        crud_user.get_boat_owner_by_phone,
        BOAT_OWNER_NOT_FOUND_DETAIL,
    )


@router.post("/login/verify", response_model=Token)
async def boat_owner_verify_otp(req: BoatOwnerVerifyOtpRequest):
    """Verify OTP: if temp_user exists, create user then return token; else login existing boat owner."""
    phone = req.mobile_number.strip()
    user = verify_otp_and_login_with_role(
        phone=phone,
        otp=req.otp,
        role_name="boat_owner",
        get_user_by_phone=crud_user.get_boat_owner_by_phone,
    )
    return _token_response(user)


# ----- Boat CRUD (owner's own boats only) -----
@router.get("/boats")
async def list_my_boats(current_user: dict = Depends(deps.get_boat_owner_user)):
    """List boats belonging to the authenticated boat owner."""
    boats = crud_user.get_boats_by_owner_id(current_user["id"])
    status_by_boat_id = trip_service.get_boat_trip_statuses([b.get("id") for b in boats])
    for boat in boats:
        status_data = status_by_boat_id.get(boat["id"])
        latest_movement_id = status_data.get("latest_movement_id") if status_data else None
        boat["latest_movement_id"] = latest_movement_id
        if not latest_movement_id:
            boat["boat_status"] = "No movement"
            continue

        trip_status = status_data.get("trip_status", "docked")
        boat["boat_status"] = "At sea" if trip_status == "sailing" else "At harbour"
    return {"success": True, "boats": boats}


@router.post("/boats", status_code=status.HTTP_201_CREATED)
async def create_boat(
    boat_name: str = Form(..., description="Name of the boat"),
    boat_type: str = Form(..., description="Type of the boat"),
    boat_number: str = Form(..., description="Boat registration number"),
    harbor_name: str = Form("mumbai", description="Harbor name (default: mumbai)"),
    document: UploadFile = File(None, description="Boat document (PDF or image: JPEG/PNG), optional"),
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Add a boat for the authenticated boat owner. Optionally upload a document (PDF or image)."""
    data = {
        "boat_name": boat_name.strip(),
        "boat_type": boat_type.strip(),
        "boat_number": boat_number.strip(),
        "harbor_name": harbor_name.strip() if harbor_name else "mumbai",
        "boat_document": None,
        "boat_document_content_type": None,
        "boat_document_filename": None,
    }
    boat_id = crud_user.create_boat(current_user["id"], data)
    if not boat_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create boat")
    if document and document.filename:
        content = await document.read()
        content_type = document.content_type or "application/octet-stream"
        if content_type not in ALLOWED_BOAT_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document must be PDF or image (JPEG/PNG). Got: {content_type}",
            )
        result = save_boat_document(boat_id, content, content_type, document.filename)
        if result:
            path, ct, name = result
            crud_user.update_boat(boat_id, {"boat_document": path, "boat_document_content_type": ct, "boat_document_filename": name})
    boat = crud_user.get_boat_by_id(boat_id)
    return {"success": True, "boat": boat}


@router.get("/boats/{boat_id}")
async def get_my_boat(boat_id: str, current_user: dict = Depends(deps.get_boat_owner_user)):
    """Get one boat; must belong to the authenticated boat owner."""
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat or boat["boat_owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    status_data = trip_service.get_boat_trip_status(boat_id) or {}
    latest_movement_id = status_data.get("latest_movement_id")
    boat["latest_movement_id"] = latest_movement_id
    if not latest_movement_id:
        boat["boat_status"] = "No movement"
        return {"success": True, "boat": boat}

    trip_status = status_data.get("trip_status", "docked")
    boat["boat_status"] = "At sea" if trip_status == "sailing" else "At harbour"
    return {"success": True, "boat": boat}


def _inventory_to_list(inv: Optional[dict]) -> list:
    """Convert boat_movement_inventory dict to TripDetailsInventoryItem list."""
    if not inv:
        return []
    items = []
    if inv.get("diesel_liters") is not None:
        items.append(
            TripDetailsInventoryItem(type="diesel", quantity=float(inv["diesel_liters"]), unit="Liters")
        )
    if inv.get("ice_blocks") is not None:
        items.append(
            TripDetailsInventoryItem(type="ice", quantity=float(inv["ice_blocks"]), unit="Kg")
        )
    if inv.get("fishing_net_count") is not None:
        items.append(
            TripDetailsInventoryItem(type="fishing_nets", quantity=float(inv["fishing_net_count"]), unit="count")
        )
    plastic = (inv.get("plastic_bottle_count") or 0) + (inv.get("plastic_bag_count") or 0)
    if plastic > 0:
        items.append(
            TripDetailsInventoryItem(type="plastic_items", quantity=float(plastic), unit="count")
        )
    return items


def _crew_to_list(crew: list) -> list:
    """Convert crew_members from trip_service to TripDetailsCrewMember list."""
    return [
        TripDetailsCrewMember(
            id=c["id"],
            name=c["name"],
            role="Pilot" if c.get("is_pilot") else "Crew",
        )
        for c in crew
    ]


@router.get(
    "/boats/{boat_id}/trip-details",
    response_model=Union[TripDetailsAtSeaResponse, TripDetailsAtHarbourResponse],
)
async def get_boat_trip_details(
    boat_id: str,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """
    Get trip details for boat owner. Returns different response based on latest movement:
    - If latest movement is departure -> At Sea response (current trip, inventory, crew)
    - If latest movement is arrival or partial_arrival -> At Harbour response (arrival info, items at departure, crew).
    Missing items, missing crew, and unidentified crew are empty until persistence is added.
    """
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat or boat["boat_owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")

    status_data = trip_service.get_boat_trip_status(boat_id)
    if not status_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")

    trip_status = status_data.get("trip_status", "docked")
    latest_movement_id = status_data.get("latest_movement_id")

    if not latest_movement_id or trip_status == "docked":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No trip data for this boat",
        )

    boat_number = boat.get("boat_number") or ""
    boat_name = boat.get("boat_name")
    vessel_type = boat.get("boat_type")

    if trip_status == "sailing":
        # At Sea: departure, inventory, crew
        dep_details = status_data.get("departure_details") or {}
        dep_at = dep_details.get("departure_at")
        from_port = dep_details.get("from_port") or boat.get("harbor_name") or "Unknown"
        if not dep_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Departure details not found")

        inv = trip_service.get_departure_inventory(latest_movement_id)
        crew_raw = trip_service.get_departure_crew_with_details(latest_movement_id)
        crew_count = status_data.get("departure_details", {}).get("crew_count") or len(crew_raw)

        return TripDetailsAtSeaResponse(
            view_type="at_sea",
            boat_id=boat_id,
            boat_number=boat_number,
            boat_name=boat_name,
            trip_status="current_trip",
            departure=TripDetailsDeparture(departure_at=dep_at, from_port=from_port),
            vessel_type=vessel_type,
            total_crew=crew_count,
            inventory_list=_inventory_to_list(inv),
            crew_members=_crew_to_list(crew_raw),
        )

    # At Harbour: arrival or partial_arrival
    movement = trip_service.get_movement_with_departure_arrival(latest_movement_id, boat_id)
    if not movement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movement not found")

    movement_type = movement.get("movement_type")
    crew_raw = trip_service.get_departure_crew_with_details(latest_movement_id)
    inv = trip_service.get_departure_inventory(latest_movement_id)
    crew_count = movement.get("crew_count") or len(crew_raw)

    departure = None
    arrival = None

    harbor_name = movement.get("harbor_name") or "Unknown"
    port_name = movement.get("port_name") or harbor_name

    if movement_type == "arrival":
        dep_at = movement.get("departure_at") or movement.get("movement_at")
        arr_at = movement.get("movement_at")
        if dep_at:
            departure = TripDetailsDeparture(
                departure_at=dep_at,
                from_port=port_name,
            )
        if arr_at:
            arrival = TripDetailsArrival(
                arrival_at=arr_at,
                to_port=harbor_name,
            )
    elif movement_type == "partial_arrival":
        arr_at = movement.get("movement_at")
        if arr_at:
            arrival = TripDetailsArrival(
                arrival_at=arr_at,
                to_port=port_name or harbor_name,
            )

    return TripDetailsAtHarbourResponse(
        view_type="at_harbour",
        boat_id=boat_id,
        boat_number=boat_number,
        boat_name=boat_name,
        trip_status="arrived",
        departure=departure,
        arrival=arrival,
        vessel_type=vessel_type,
        total_crew=crew_count,
        list_of_items_while_departure=_inventory_to_list(inv),
        list_of_missing_items=[],
        missing_crew_members=[],
        unidentified_crew_members=[],
        reason_for_loss=None,
        additional_details=None,
        crew_members=_crew_to_list(crew_raw),
        partial_arrival_reason=movement.get("partial_arrival_reason"),
        partial_arrival_details=movement.get("partial_arrival_details"),
    )


@router.put("/boats/{boat_id}")
async def update_my_boat(
    boat_id: str,
    boat_name: str = Form(None, description="Name of the boat (optional)"),
    boat_type: str = Form(None, description="Type of the boat (optional)"),
    boat_number: str = Form(None, description="Boat registration number (optional)"),
    harbor_name: str = Form(None, description="Harbor name (optional)"),
    document: UploadFile = File(None, description="Replace boat document with PDF or image (optional)"),
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Update a boat; must belong to the authenticated boat owner. Optionally upload a new document."""
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat or boat["boat_owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    update_dict = {}
    if boat_name is not None and boat_name.strip():
        update_dict["boat_name"] = boat_name.strip()
    if boat_type is not None and boat_type.strip():
        update_dict["boat_type"] = boat_type.strip()
    if boat_number is not None and boat_number.strip():
        update_dict["boat_number"] = boat_number.strip()
    if harbor_name is not None and harbor_name.strip():
        update_dict["harbor_name"] = harbor_name.strip()
    if document and document.filename:
        content = await document.read()
        content_type = document.content_type or "application/octet-stream"
        if content_type not in ALLOWED_BOAT_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document must be PDF or image (JPEG/PNG). Got: {content_type}",
            )
        result = save_boat_document(boat_id, content, content_type, document.filename)
        if result:
            path, ct, name = result
            update_dict["boat_document"] = path
            update_dict["boat_document_content_type"] = ct
            update_dict["boat_document_filename"] = name
    if update_dict:
        ok = crud_user.update_boat(boat_id, update_dict)
        if not ok:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update boat")
    return {"success": True, "boat": crud_user.get_boat_by_id(boat_id)}


@router.delete("/boats/{boat_id}")
async def delete_my_boat(boat_id: str, current_user: dict = Depends(deps.get_boat_owner_user)):
    """Soft delete a boat; must belong to the authenticated boat owner."""
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat or boat["boat_owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    ok = crud_user.delete_boat(boat_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete boat")
    return {"success": True, "message": "Boat deleted"}


# ----- Delivery (scan QR and record) -----
@router.post("/deliveries/scan", response_model=ScanDeliveryResponse)
async def scan_delivery_qr(
    body: ScanDeliveryRequest,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """
    Resolve QR payload to delivery details. Boat owner scans buyer's QR code.
    Provide either qr_payload (JSON string) or auction_id + buyer_id.
    """
    auction_id = body.auction_id
    buyer_id = body.buyer_id

    if body.qr_payload:
        try:
            payload = json.loads(body.qr_payload)
            auction_id = payload.get("auction_id") or auction_id
            buyer_id = payload.get("buyer_id") or buyer_id
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid qr_payload: expected JSON with auction_id and buyer_id",
            )

    if not auction_id or not buyer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide auction_id and buyer_id, or qr_payload",
        )

    detail, err = boat_owner_delivery_service.get_delivery_by_qr(
        auction_id=auction_id,
        buyer_id=buyer_id,
        boat_owner_id=current_user["id"],
    )
    if err:
        if "does not belong" in err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err)

    return ScanDeliveryResponse(**detail)


@router.post("/deliveries/{auction_id}/record", response_model=RecordDeliveryResponse)
async def record_delivery(
    auction_id: str,
    body: RecordDeliveryRequest,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Record delivered quantity for an auction. Only the boat owner (seller) can record."""
    _, err = boat_owner_delivery_service.record_delivery(
        auction_id=auction_id,
        boat_owner_id=current_user["id"],
        delivered_quantity=body.delivered_quantity,
    )
    if err:
        if "does not belong" in err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    return RecordDeliveryResponse(success=True, message="Delivery recorded successfully")


@router.get("/deliveries/initiate/{auction_id}", response_model=InitiateDeliveryResponse)
async def initiate_delivery_details(
    auction_id: str,
    current_user: dict = Depends(deps.get_boat_owner_or_agent_user),
):
    """Get initiate-delivery details for a completed auction (winner + bid + quantities)."""
    if current_user.get("role") == "agent":
        detail, err = boat_owner_delivery_service.get_initiate_delivery_for_auction_by_agent(
            auction_id=auction_id,
            agent_id=current_user["id"],
        )
    else:
        detail, err = boat_owner_delivery_service.get_initiate_delivery_for_auction(
            auction_id=auction_id,
            boat_owner_id=current_user["id"],
        )
    if err:
        if "does not belong" in err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err)
        if "no winner" in err.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err)

    return InitiateDeliveryResponse(**detail)


@router.get(
    "/deliveries",
    response_model=list[PendingDeliveryItem],
)
async def list_pending_deliveries(
    status_filter: Optional[str] = Query("pending", alias="status"),
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """
    List deliveries for the authenticated boat owner filtered by status.
    Query param: ?status=pending|completed
    """
    status_value = (status_filter or "pending").strip().lower()
    if status_value not in {"pending", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Allowed values: pending, completed",
        )

    items = boat_owner_delivery_service.get_deliveries_for_boat_owner(
        boat_owner_id=current_user["id"],
        status_filter=status_value,
    )
    return items


# ----- Bidding Requests (boat owner side) -----
@router.get("/bidding-requests", response_model=BiddingRequestListResponse)
async def list_bidding_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    boat_id: Optional[str] = Query(None, alias="boat_id"),
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """List bidding requests for the authenticated boat owner, optionally filtered by boat."""
    requests = bidding_service.list_bidding_requests_for_owner(
        boat_owner_id=current_user["id"],
        status_filter=status_filter,
        boat_id=boat_id,
    )
    return BiddingRequestListResponse(
        success=True,
        total=len(requests),
        bidding_requests=[BiddingRequestItem(**r) for r in requests],
    )


@router.put("/bidding-requests/{request_id}", response_model=BiddingRequestResponse)
async def respond_to_bidding_request(
    request_id: str,
    body: BiddingRequestAction,
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """
    Boat owner approves or rejects a bidding request.
    Pass {"status": "approved"} or {"status": "rejected"}.
    """
    result, err = bidding_service.respond_to_bidding_request(
        request_id=request_id,
        boat_owner_id=current_user["id"],
        new_status=body.status,
    )
    if err:
        if "not found" in err.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err)
        if "already" in err.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    boat_label = result.get("boat_number") or result.get("boat_name") or ""
    agent_name = result.get("agent_name") or "Agent"
    action_label = "approved" if body.status == "approved" else "rejected"

    notification_service.create_notification(
        notification_type="bidding_request_response",
        title=f"Bidding request {action_label} for {boat_label}",
        message=f"Boat owner has {action_label} {agent_name}'s bidding request for {boat_label}.",
        metadata={
            "bidding_request_id": request_id,
            "boat_id": result.get("boat_id"),
            "boat_number": result.get("boat_number"),
            "agent_id": result.get("agent_id"),
            "status": body.status,
        },
        recipient_role="agent",
        priority="medium",
    )

    return BiddingRequestResponse(
        success=True,
        message=f"Bidding request {action_label}",
        bidding_request=BiddingRequestItem(**result),
    )
