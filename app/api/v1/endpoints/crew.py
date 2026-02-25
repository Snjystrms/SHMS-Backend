import json
import uuid
import numpy as np
from typing import Dict, List, Optional
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.responses import Response
from app.services import face_service
from app.services import user_service as crud_user
from app.core.config import settings
from app.api import deps
from app.schemas.crew import (
    CrewMemberResponse,
    CrewMemberUpdate,
    CrewVerifyOtpRequest,
    CrewGroupScanResponse,
    CrewFaceScanResult,
    OfficerRegisterUserRequest,
)
from app.schemas.user import ForgotPasswordRequest
from app.utils.otp_helpers import get_sms
from app.utils.uploads import save_crew_scan_image


router = APIRouter()

# In-memory store for cropped face images (crop_id -> PNG bytes). Served on demand; not saved to disk.
_scan_result_crops: Dict[str, bytes] = {}

@router.get("/crew-members", response_model=List[CrewMemberResponse])
async def list_crew_members(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """List all crew members."""
    return face_service.get_all_crew_members(skip=skip, limit=limit)

@router.get("/crew-members/{crew_member_id}", response_model=CrewMemberResponse)
async def get_crew_member(
    crew_member_id: str,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """Get details of a specific crew member."""
    crew_member = face_service.get_crew_member_by_id(crew_member_id)
    if not crew_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crew member not found"
        )
    return crew_member

@router.post("/crew-members/register", status_code=status.HTTP_201_CREATED)
async def officer_register_user(
    body: OfficerRegisterUserRequest,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Officer registers a user with minimum info. Compulsory: name, aadhaar_number.
    Optional: contact_number, emergency_contact_number, is_pilot.
    is_register is always set to false for this flow.
    """
    name = (body.name or "").strip()
    aadhaar = (body.aadhaar_number or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required",
        )
    if not aadhaar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aadhaar number is required",
        )
    crew_member_id = face_service.register_user_minimal(
        name=name,
        aadhaar_number=aadhaar,
        contact_number=body.contact_number,
        emergency_contact_number=body.emergency_contact_number,
        is_pilot=body.is_pilot,
    )
    if not crew_member_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A crew member with this Aadhaar number already exists",
        )
    crew_member = face_service.get_crew_member_by_id(crew_member_id)
    return {
        "success": True,
        "id": crew_member_id,
        "message": "User registered successfully (is_register=false)",
        "crew_member": crew_member,
    }


@router.post("/crew-members", status_code=status.HTTP_201_CREATED)
async def create_crew_member(
    name: str = Form(...),
    aadhaar_number: str = Form(None),
    contact_number: str = Form(...),
    emergency_contact_number: str = Form(None),
    is_pilot: str = Form("false"),
    file: UploadFile = File(...),
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """
    Step 1: Submit crew details and face photo. OTP is sent to contact_number.
    Crew member is created only after OTP verification via POST /crew-members/verify-otp.
    """
    image_bytes = await file.read()
    embedding = face_service.get_embedding(image_bytes)

    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image or no face detected"
        )

    # Check for duplicates
    existing_user_id, existing_username, distance = face_service.find_match(embedding)
    if distance is not None and distance < settings.FACE_DUPLICATE_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Face already registered as {existing_username} ({existing_user_id})"
        )

    phone = (contact_number or "").strip()
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact number (phone) is required to send OTP"
        )

    is_pilot_val = (is_pilot or "").strip().lower() in ("true", "1", "on", "yes")
    if not crud_user.create_pending_crew(
        phone=phone,
        name=name,
        aadhaar_number=aadhaar_number,
        emergency_contact_number=emergency_contact_number,
        is_pilot=is_pilot_val,
        embedding_list=embedding.tolist(),
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save registration"
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
        "message": "OTP sent to your mobile. Verify to complete crew member registration.",
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }


@router.post("/crew-members/verify-otp", status_code=status.HTTP_201_CREATED)
async def verify_crew_otp(
    req: CrewVerifyOtpRequest,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """
    Step 2: Verify OTP sent to the crew member's phone. On success, creates the crew member and returns details.
    """
    phone = req.mobile_number.strip()
    if not crud_user.verify_otp(phone, req.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    pending = crud_user.get_pending_crew_by_phone(phone)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending crew registration for this phone. Please submit the form again."
        )

    emb = pending["embedding"]
    if isinstance(emb, str):
        emb = json.loads(emb)
    embedding = np.array(emb, dtype=np.float32)
    user_id = face_service.register_user(
        pending["name"],
        embedding,
        aadhaar_number=pending["aadhaar_number"],
        contact_number=pending["phone"],
        emergency_contact_number=pending["emergency_contact_number"],
        is_pilot=pending["is_pilot"],
    )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register crew member"
        )
    crud_user.delete_pending_crew_by_phone(phone)

    return {
        "success": True,
        "id": user_id,
        "name": pending["name"],
        "aadhaar_number": pending["aadhaar_number"],
        "contact_number": pending["phone"],
        "emergency_contact_number": pending["emergency_contact_number"],
        "is_pilot": pending["is_pilot"],
        "message": "Crew member created successfully"
    }


@router.post("/crew-members/resend-otp")
async def resend_crew_otp(
    req: ForgotPasswordRequest,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """Resend OTP for pending crew registration. Only valid if a pending registration exists for this phone."""
    phone = req.mobile_number.strip()
    pending = crud_user.get_pending_crew_by_phone(phone)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending crew registration for this phone. Please submit the form again."
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
        "message": "OTP resent.",
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }

@router.put("/crew-members/{crew_member_id}", response_model=dict)
async def update_crew_member(
    crew_member_id: str,
    crew_member_data: CrewMemberUpdate,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """Update a crew member's details (name)."""
    # Check if exists
    existing_member = face_service.get_crew_member_by_id(crew_member_id)
    if not existing_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crew member not found"
        )
    
    
    result = face_service.update_crew_member(
        crew_member_id, 
        name=crew_member_data.name,
        aadhaar_number=crew_member_data.aadhaar_number,
        contact_number=crew_member_data.contact_number,
        emergency_contact_number=crew_member_data.emergency_contact_number,
        is_pilot=crew_member_data.is_pilot
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update crew member"
        )
    
    return {"success": True, "message": "Crew member updated successfully"}


@router.get(
    "/crew-members/scan-result/{crop_id}/crop",
    name="get_scan_result_crop",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}, "description": "Cropped face/person PNG"}},
)
async def get_scan_result_crop(crop_id: str):
    """Serve a cropped face/person image for a scan result. No auth required."""
    png_bytes = _scan_result_crops.get(crop_id)
    if png_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crop image not found",
        )
    return Response(content=png_bytes, media_type="image/png")


@router.post(
    "/crew-members/scan-group-photo",
    response_model=CrewGroupScanResponse,
)
async def scan_group_photo(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Port officer uploads a group photo to identify crew.

    The image is processed using the configured InsightFace pipeline.
    Returns JSON with faces (no bbox), counts, and annotated_image_url (URL to fetch the processed PNG).
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file is empty",
        )

    raw_result = face_service.identify_faces_in_image(image_bytes)
    if raw_result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image data",
        )

    faces_payload = raw_result.get("faces", [])
    summary = raw_result.get("summary", {}) or {}

    # Annotated image with boxes drawn (PIL): green = match, red = no match
    annotated_bytes = face_service.draw_face_boxes_on_image(image_bytes, faces_payload)

    # Save annotated image to uploads folder and return URL (served by StaticFiles at /uploads/...)
    annotated_image_url: Optional[str] = None
    if annotated_bytes:
        url_path = save_crew_scan_image(annotated_bytes)
        if url_path:
            base = str(request.base_url).rstrip("/")
            annotated_image_url = f"{base}{url_path}"

    faces: List[CrewFaceScanResult] = []
    base_url = str(request.base_url).rstrip("/")
    for f in faces_payload:
        crew_member_data = f.get("crew_member")
        crew_member_obj = None
        if crew_member_data:
            crew_member_obj = CrewMemberResponse(**crew_member_data)

        crop_image_url: Optional[str] = None
        bbox = f.get("bbox")
        if bbox and len(bbox) == 4:
            crop_bytes = face_service.crop_face_from_image(image_bytes, bbox)
            if crop_bytes:
                crop_id = str(uuid.uuid4())
                _scan_result_crops[crop_id] = crop_bytes
                path = request.url_for("get_scan_result_crop", crop_id=crop_id)
                path_str = str(path)
                crop_image_url = path_str if (path_str.startswith("http://") or path_str.startswith("https://")) else f"{base_url}{path_str}"

        faces.append(
            CrewFaceScanResult(
                det_score=f.get("det_score", 0.0),
                distance=f.get("distance"),
                is_match=bool(f.get("is_match")),
                crew_member=crew_member_obj,
                crop_image_url=crop_image_url,
            )
        )

    total_faces = int(summary.get("total_faces", len(faces)))
    matched_count = int(summary.get("matched_count", 0))
    unmatched_count = int(summary.get("unmatched_count", total_faces - matched_count))

    return CrewGroupScanResponse(
        faces=faces,
        total_faces=total_faces,
        matched_count=matched_count,
        unmatched_count=unmatched_count,
        annotated_image_url=annotated_image_url,
    )

@router.delete("/crew-members/{crew_member_id}")
async def delete_crew_member(
    crew_member_id: str,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """Delete a crew member."""
    # Check if exists
    existing_member = face_service.get_crew_member_by_id(crew_member_id)
    if not existing_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crew member not found"
        )
    
    result = face_service.delete_crew_member(crew_member_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete crew member"
        )
    
    return {"success": True, "message": "Crew member deleted successfully"}
