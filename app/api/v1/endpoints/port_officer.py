"""Port officer endpoints: boat identification by registration number."""
import urllib.request
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form, Request
from app.api import deps
from app.core.config import settings
from app.services import user_service, trip_service, face_service, notification_service, boat_scan_service
from app.schemas.user import BoatIdentifyResponse, PendingBoatRegisterRequest, BoatScanResponse
from app.schemas.crew import (
    CrewScannedHistoryResponse,
    CrewScannedHistoryItem,
    CrewHistoryDateFilter,
)
from app.schemas.trip import (
    BoatTripStatusResponse,
    BoatMovementCreate,
    BoatMovementResponse,
    BoatMovementCrewCreate,
    BoatMovementCrewResponse,
    BoatMovementInventoryCreate,
    BoatMovementInventoryResponse,
    ArrivalCrewCheckResponse,
    ArrivalCrewMemberStatus,
    ArrivalUnidentifiedEntry,
    ArrivalInventoryCheckRequest,
    ArrivalInventoryCheckResponse,
    ArrivalInventoryCheckSummary,
    ArrivalInventoryItemDiscrepancy,
    InventoryCategorySummary,
    BoatMovementHistoryResponse,
    BoatMovementHistoryItem,
    HistoryDateFilter,
)
from app.schemas.dashboard import (
    PortOfficerDashboardResponse,
    PortOfficerDashboardUser,
    TodayActivity,
)
from app.utils.sms import get_sms_provider
from app.utils.uploads import save_crew_scan_image
from app.utils.url_helpers import resolve_image_url


def _fetch_image_bytes_from_url(image_url: str) -> Optional[bytes]:
    """Fetch image bytes from full URL or from local path (e.g. /uploads/...)."""
    if not image_url or not image_url.strip():
        return None
    url = image_url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SHMS-Backend/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception:
            return None
    if url.startswith("/"):
        import os
        local_path = os.path.join(os.getcwd(), url.lstrip("/"))
        if os.path.isfile(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception:
                return None
    return None


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


@router.get("/dashboard", response_model=PortOfficerDashboardResponse)
async def get_port_officer_dashboard(
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Port officer dashboard: current user info and today's activity summary
    (departures, arrivals, crew registration, crew verification counts).
    """
    counts = trip_service.get_dashboard_today_counts()
    return PortOfficerDashboardResponse(
        user=PortOfficerDashboardUser(
            id=current_user.get("id", ""),
            name=current_user.get("name", ""),
            shift_active=True,
        ),
        today_activity=TodayActivity(
            departures=counts["departures"],
            arrivals=counts["arrivals"],
            crew_registration=counts["crew_registration"],
            crew_verification=counts["crew_verification"],
            updated_at=counts["updated_at"],
        ),
    )


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
    is_pending = False
    if not boat:
        boat = user_service.get_boat_by_number(boat_number)
        if not boat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Boat not found",
            )
        is_pending = True

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
        is_pending_registration=is_pending,
    )
    
@router.post("/boats/scan-number", response_model=BoatScanResponse)
async def scan_boat_number(
    file: UploadFile = File(...),
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Scan a boat image to extract the registration number using OCR.
    Accepts an image upload (JPEG/PNG). Returns the detected Indian fishing
    boat registration number and, if found in the database, full boat details.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file is required",
        )
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    result = boat_scan_service.scan_boat_number(image_bytes)
    boat_number = result.get("boat_number")

    boat_details = None
    is_pending = False
    if boat_number:
        boat = user_service.get_boat_by_number_with_owner(boat_number)
        if not boat:
            boat = user_service.get_boat_by_number(boat_number)
            if boat:
                is_pending = True
        if boat:
            status_data = trip_service.get_boat_trip_status(boat["id"])
            last_departure = None
            if status_data and status_data.get("departure_details"):
                dep_at = status_data["departure_details"]["departure_at"]
                last_departure = dep_at.strftime("%b %d, %I:%M %p")
            boat_details = BoatIdentifyResponse(
                registration_no=boat["boat_number"],
                vessel_name=boat.get("boat_name"),
                owner_name=boat.get("owner_name", ""),
                home_harbor=boat.get("harbor_name"),
                boat_type=boat.get("boat_type"),
                last_logged_departure=last_departure,
                boat_id=boat["id"],
                is_pending_registration=is_pending,
            )

    if not boat_number:
        message = "No boat registration number detected in the image"
    elif boat_details:
        message = (
            f"Boat {boat_number} identified and found in database (pending registration)"
            if is_pending
            else f"Boat {boat_number} identified and found in database"
        )
    else:
        message = f"Boat number {boat_number} detected but not found in database"

    return BoatScanResponse(
        success=boat_number is not None,
        boat_number=boat_number,
        confidence=result.get("confidence"),
        all_detected_text=result.get("all_detected_text", []),
        boat=boat_details,
        message=message,
    )


@router.get("/boats/{boat_id}/trip-status", response_model=BoatTripStatusResponse)
async def get_boat_trip_status(
    boat_id: str,
    request: Request,
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
    request_base = str(request.base_url)
    if status_data.get("departure_details") and status_data["departure_details"].get("image_url") and not status_data["departure_details"]["image_url"].startswith("http"):
        status_data["departure_details"]["image_url"] = resolve_image_url(status_data["departure_details"]["image_url"], request_base)
    if status_data.get("last_movement_image_url") and not status_data["last_movement_image_url"].startswith("http"):
        status_data["last_movement_image_url"] = resolve_image_url(status_data["last_movement_image_url"], request_base)
    return BoatTripStatusResponse(**status_data)


@router.get(
    "/movements/history",
    response_model=BoatMovementHistoryResponse,
)
async def get_movement_history(
    request: Request,
    movement_type: str,
    date_filter: HistoryDateFilter = "today",
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    History API for boat movements (e.g. Departure History tab).
    Filters by movement_type (departure/arrival/partial_arrival) and date_filter
    (today, last_7_days, last_30_days).
    """
    records_raw = trip_service.get_movement_history(
        movement_type=movement_type,
        date_filter=date_filter,
    )
    request_base = str(request.base_url)
    for r in records_raw:
        if r.get("image_url") and not r["image_url"].startswith("http"):
            r["image_url"] = resolve_image_url(r["image_url"], request_base)
    records = [BoatMovementHistoryItem(**r) for r in records_raw]
    return BoatMovementHistoryResponse(
        movement_type=movement_type,
        date_filter=date_filter,
        total_records=len(records),
        records=records,
    )


@router.get(
    "/crew-scanned/history",
    response_model=CrewScannedHistoryResponse,
)
async def get_crew_scanned_history(
    request: Request,
    date_filter: CrewHistoryDateFilter = "today",
    is_register: Optional[bool] = None,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Crew Scanned history for an officer.
    Returns crew name, boat name, crew id, boat number, is_pilot,
    phone number, aadhaar number and emergency contact number.
    """
    officer_id = current_user.get("id")
    records_raw = trip_service.get_scanned_crew_history(
        officer_user_id=officer_id,
        date_filter=date_filter,
        is_register=is_register,
    )
    # Resolve relative image_url to absolute URL for Android/client compatibility
    request_base = str(request.base_url)
    for r in records_raw:
        if r.get("image_url") and not r["image_url"].startswith("http"):
            r["image_url"] = resolve_image_url(r["image_url"], request_base)
    records = [CrewScannedHistoryItem(**r) for r in records_raw]
    return CrewScannedHistoryResponse(
        date_filter=date_filter,
        total_records=len(records),
        records=records,
    )


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
    - Departure: Creates a new movement (new movement id).
    - Arrival: Updates the existing open departure for this boat (same movement id); does not create a new record.
    - Partial arrival: Creates a new movement when no departure exists; partial_arrival_reason is required.
      If reason is 'other', partial_arrival_details is required.
    """
    movement, err = trip_service.create_boat_movement(
        boat_id=boat_id,
        movement_type=body.movement_type,
        movement_at=body.movement_at,
        logged_by_user_id=current_user.get("id"),
        partial_arrival_reason=body.partial_arrival_reason,
        partial_arrival_details=body.partial_arrival_details,
        image_url=body.image_url,
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

    # Create notifications for admin and boat owner about this movement.
    movement_type = movement.get("movement_type")
    boat = user_service.get_boat_by_id(boat_id)
    boat_number = boat.get("boat_number") if boat else None
    boat_name = boat.get("boat_name") if boat else None
    boat_owner_id = boat.get("boat_owner_id") if boat else None

    if movement_type in {"departure", "arrival", "partial_arrival"}:
        if movement_type == "departure":
            title_suffix = "Departure logged"
            message_suffix = "has departed."
        elif movement_type == "arrival":
            title_suffix = "Arrival logged"
            message_suffix = "has arrived."
        else:
            title_suffix = "Partial arrival logged"
            message_suffix = "has logged a partial arrival."

        boat_label = boat_number or boat_name or boat_id
        movement_at = movement.get("movement_at")
        movement_at_str = movement_at.isoformat() if hasattr(movement_at, "isoformat") else None

        metadata = {
            "boat_id": boat_id,
            "boat_number": boat_number,
            "boat_name": boat_name,
            "boat_owner_id": boat_owner_id,
            "movement_id": movement.get("id"),
            "movement_type": movement_type,
            "movement_at": movement_at_str,
            "partial_arrival_reason": movement.get("partial_arrival_reason"),
            "partial_arrival_details": movement.get("partial_arrival_details"),
        }

        # Admin notification
        notification_service.create_notification(
            notification_type=f"boat_{movement_type}",
            title=f"Boat {boat_label}: {title_suffix}",
            message=f"Boat {boat_label} {message_suffix}",
            metadata=metadata,
            priority="medium" if movement_type in {"departure", "arrival"} else "high",
        )

        # Boat owner notification (if linked owner exists)
        if boat_owner_id:
            notification_service.create_notification(
                notification_type=f"boat_{movement_type}",
                title=f"Your boat {boat_label}: {title_suffix}",
                message=f"Your boat {boat_label} {message_suffix}",
                metadata=metadata,
                recipient_role="boat_owner",
                priority="normal",
            )

    return BoatMovementResponse(**movement)


@router.post(
    "/movements/{movement_id}/crew",
    response_model=BoatMovementCrewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_boat_movement_crew(
    movement_id: str,
    body: BoatMovementCrewCreate,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Port officer attaches crew list for a specific departure movement (trip).
    Uses movement_id returned by the departure creation API.
    Pass crop_id per crew when attaching from scan-group-photo for face image in history.
    """
    crew_ids = [item.crew_member_id for item in body.crew_members]
    crew_crop_ids = {
        item.crew_member_id: item.crop_id
        for item in body.crew_members
        if item.crop_id
    }
    result, err = trip_service.set_boat_movement_crew(
        movement_id=movement_id,
        crew_member_ids=crew_ids,
        unidentified_count=0,
        crew_crop_ids=crew_crop_ids,
    )
    if err:
        if "Departure movement not found" in err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to attach crew to movement",
        )
    return BoatMovementCrewResponse(**result)


@router.post(
    "/movements/{movement_id}/inventory",
    response_model=BoatMovementInventoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_boat_movement_inventory(
    movement_id: str,
    body: BoatMovementInventoryCreate,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Port officer records diesel, ice, fishing net count and plastic items for a trip.
    Uses movement_id (the departure movement for this trip).
    """
    result, err = trip_service.set_boat_movement_inventory(
        movement_id=movement_id,
        diesel_liters=body.diesel_liters,
        ice_blocks=body.ice_blocks,
        fishing_net_count=body.fishing_net_count,
        plastic_bottle_count=body.plastic_bottle_count,
        plastic_bag_count=body.plastic_bag_count,
    )
    if err:
        if "Departure movement not found" in err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to attach inventory to movement",
        )
    return BoatMovementInventoryResponse(**result)


@router.get(
    "/movements/{movement_id}/inventory",
    response_model=BoatMovementInventoryResponse,
)
async def get_boat_movement_inventory(
    movement_id: str,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Fetch inventory details (diesel, ice, nets, plastics) for a specific trip movement (departure or arrival).
    """
    movement = trip_service.get_trip_movement_by_id(movement_id)
    if not movement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movement not found",
        )

    inv = trip_service.get_departure_inventory(movement_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found for this movement",
        )

    return BoatMovementInventoryResponse(
        movement_id=movement_id,
        boat_id=movement["boat_id"],
        diesel_liters=inv.get("diesel_liters"),
        ice_blocks=inv.get("ice_blocks"),
        fishing_net_count=inv.get("fishing_net_count"),
        plastic_bottle_count=inv.get("plastic_bottle_count"),
        plastic_bag_count=inv.get("plastic_bag_count"),
        success=True,
        message="Inventory fetched successfully.",
    )


@router.post(
    "/movements/{movement_id}/arrival/crew/scan",
    response_model=ArrivalCrewCheckResponse,
)
async def arrival_crew_scan(
    movement_id: str,
    request: Request,
    file: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Arrival crew identification: scan image (upload or image_url) and compare with departure crew.
    Uses movement_id (the trip movement — same id for departure and after arrival).
    - Present: crew was at departure and identified in arrival scan.
    - Missing: crew was at departure but not identified in arrival scan.
    - Unidentified: face detected at arrival that does not match any crew from this trip's departure (e.g. from another boat).
    Provide either file or image_url; if both provided, file takes precedence.
    """
    image_bytes: Optional[bytes] = None
    if file and file.filename:
        image_bytes = await file.read()
    if not image_bytes and image_url:
        image_bytes = _fetch_image_bytes_from_url(image_url)
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either an image file upload or image_url",
        )

    movement = trip_service.get_trip_movement_by_id(movement_id)
    if not movement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movement not found or not a valid trip (departure/arrival).",
        )
    boat_id = movement["boat_id"]
    departure_crew = trip_service.get_departure_crew_with_details(movement_id)
    departure_crew_ids = {c["id"] for c in departure_crew}

    raw_result = face_service.identify_faces_in_image(image_bytes)
    if raw_result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image or could not process",
        )
    faces = raw_result.get("faces", [])

    matched_ids = set()
    for f in faces:
        crew = f.get("crew_member")
        if crew and f.get("is_match") and crew.get("id") in departure_crew_ids:
            matched_ids.add(crew["id"])

    present_crew = [
        ArrivalCrewMemberStatus(
            crew_member_id=c["id"],
            name=c["name"],
            is_pilot=c.get("is_pilot", False),
            status="present",
        )
        for c in departure_crew
        if c["id"] in matched_ids
    ]
    missing_crew = [
        ArrivalCrewMemberStatus(
            crew_member_id=c["id"],
            name=c["name"],
            is_pilot=c.get("is_pilot", False),
            status="missing",
        )
        for c in departure_crew
        if c["id"] not in matched_ids
    ]
    unidentified_count = sum(
        1 for f in faces
        if not (f.get("is_match") and f.get("crew_member") and f["crew_member"].get("id") in departure_crew_ids)
    )
    unidentified_crew = [
        ArrivalUnidentifiedEntry(id=str(uuid.uuid4())) for _ in range(unidentified_count)
    ]

    # Generate annotated image with boxes for present/missing/unidentified
    annotated_image_url = None
    annotated_bytes = face_service.draw_face_boxes_on_image(image_bytes, faces)
    if annotated_bytes:
        annotated_path = save_crew_scan_image(annotated_bytes)
        if annotated_path:
            annotated_image_url = resolve_image_url(annotated_path, str(request.base_url))

    return ArrivalCrewCheckResponse(
        movement_id=movement_id,
        boat_id=boat_id,
        annotated_image_url=annotated_image_url,
        crew_at_departure=len(departure_crew),
        crew_at_arrival=len(present_crew),
        missing_crew_count=len(missing_crew),
        unidentified_count=unidentified_count,
        present_crew=present_crew,
        missing_crew=missing_crew,
        unidentified_crew=unidentified_crew,
    )


@router.post(
    "/movements/{movement_id}/arrival/inventory/check",
    response_model=ArrivalInventoryCheckResponse,
)
async def arrival_inventory_check(
    movement_id: str,
    body: ArrivalInventoryCheckRequest,
    request: Request,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Compare arrival inventory counts with departure. Returns per-item status: matched or missing.
    Uses movement_id (the trip movement — same id for departure and after arrival). Optionally provide loss_reasons for missing items.
    """
    movement = trip_service.get_trip_movement_by_id(movement_id)
    if not movement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movement not found or not a valid trip (departure/arrival).",
        )
    boat_id = movement["boat_id"]
    dep_inv = trip_service.get_departure_inventory(movement_id)

    loss_reasons = body.loss_reasons or {}
    items_spec = [
        ("diesel_liters", "Diesel (L)", body.diesel_liters, dep_inv.get("diesel_liters") if dep_inv else None),
        ("ice_blocks", "Ice blocks", body.ice_blocks, dep_inv.get("ice_blocks") if dep_inv else None),
        ("fishing_net_count", "Fishing nets", body.fishing_net_count, dep_inv.get("fishing_net_count") if dep_inv else None),
        ("plastic_bottle_count", "Plastic bottles", body.plastic_bottle_count, dep_inv.get("plastic_bottle_count") if dep_inv else None),
        ("plastic_bag_count", "Plastic bags", body.plastic_bag_count, dep_inv.get("plastic_bag_count") if dep_inv else None),
    ]
    items: list = []
    for key, label, arrival_val, dep_val in items_spec:
        dep_q = dep_val if dep_val is not None else 0
        arr_q = arrival_val if arrival_val is not None else 0
        if dep_q == 0 and arr_q == 0:
            continue
        is_missing = dep_q > arr_q
        status_val = "missing" if is_missing else "matched"
        reason_entry = loss_reasons.get(key)
        items.append(
            ArrivalInventoryItemDiscrepancy(
                item_name=label,
                departure_quantity=float(dep_q) if isinstance(dep_q, (int, float)) else None,
                arrival_quantity=float(arr_q) if isinstance(arr_q, (int, float)) else None,
                status=status_val,
                reason_for_loss=reason_entry.reason if reason_entry else None,
                additional_details=reason_entry.additional_details if reason_entry else None,
            )
        )
    all_matched = all(it.status == "matched" for it in items)

    # Build check summary for fishing nets and plastic items (bottles + bags)
    dep_net = int(dep_inv.get("fishing_net_count") or 0) if dep_inv else 0
    arr_net = int(body.fishing_net_count or 0)
    dep_plastic = int(dep_inv.get("plastic_bottle_count") or 0) + int(dep_inv.get("plastic_bag_count") or 0) if dep_inv else 0
    arr_plastic = int(body.plastic_bottle_count or 0) + int(body.plastic_bag_count or 0)
    net_matched = dep_net <= arr_net
    plastic_matched = dep_plastic <= arr_plastic
    summary = ArrivalInventoryCheckSummary(
        fishing_nets=InventoryCategorySummary(
            departure=dep_net,
            arrival=arr_net,
            status="matched" if net_matched else "missing",
            verified=net_matched,
        ),
        plastic_items=InventoryCategorySummary(
            departure=dep_plastic,
            arrival=arr_plastic,
            status="matched" if plastic_matched else "missing",
            verified=plastic_matched,
        ),
    )

    image_url = resolve_image_url(body.image_url, str(request.base_url)) if body.image_url else None

    return ArrivalInventoryCheckResponse(
        movement_id=movement_id,
        boat_id=boat_id,
        image_url=image_url,
        items=items,
        all_matched=all_matched,
        summary=summary,
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

    # Notify admin that this boat is not registered (high priority)
    notification_service.create_notification(
        notification_type="boat_not_registered",
        title="Boat not registered",
        message=f"Boat {boat_number} is not registered. SMS sent to owner ({mobile_number}).",
        metadata={
            "boat_id": boat_id,
            "boat_number": boat_number,
            "owner_mobile": mobile_number,
        },
        priority="high",
    )

    return {
        "success": True,
        "boat_id": boat_id,
        "boat_number": boat_number,
        "message": "Pending boat created. SMS sent to owner.",
    }
