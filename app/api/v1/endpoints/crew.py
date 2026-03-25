import asyncio
import json
import logging
import uuid
from urllib.parse import urlparse

import numpy as np
import requests

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
)
from app.schemas.user import ForgotPasswordRequest
from app.utils.otp_helpers import get_sms
from app.utils.uploads import save_crew_scan_image, save_crew_crop, load_crew_crop, save_crew_embedding, load_crew_embedding
from app.utils.url_helpers import resolve_image_url


router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory store for cropped face images (crop_id -> PNG bytes). Served on demand; not saved to disk.
_scan_result_crops: Dict[str, bytes] = {}
# Pre-computed embeddings from scan-group-photo (crop_id -> embedding list). Reused when registering.
_scan_result_embeddings: Dict[str, List[float]] = {}

@router.get("/crew-members", response_model=List[CrewMemberResponse])
async def list_crew_members(
    skip: int = 0,
    limit: int = 10,
    is_register: Optional[bool] = None,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """List all crew members."""
    return face_service.get_all_crew_members(skip=skip, limit=limit, is_register=is_register)

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

@router.post("/crew-members/detect-face")
async def detect_crew_face(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Accept a crew member photo from the frontend. Returns whether a face was detected
    and a URL to the cropped face image when a face is found.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file is empty",
        )

    face_detected, crop_bytes = face_service.detect_face_and_crop(image_bytes)

    crop_image_url: Optional[str] = None
    if face_detected and crop_bytes:
        crop_id = str(uuid.uuid4())
        _scan_result_crops[crop_id] = crop_bytes
        save_crew_crop(crop_id, crop_bytes)
        path = request.url_for("get_scan_result_crop", crop_id=crop_id)
        path_str = str(path)
        crop_image_url = resolve_image_url(path_str, str(request.base_url))

    return {
        "face_detected": face_detected,
        "crop_image_url": crop_image_url,
    }


@router.post("/crew-members/register", status_code=status.HTTP_201_CREATED)
async def officer_register_user(
    request: Request,
    current_user: dict = Depends(deps.get_admin_or_officer_user),
):
    """
    Officer registers a user with minimum info. Compulsory: name, aadhaar_number.
    Optional: contact_number, emergency_contact_number, is_pilot.
    Face embedding: pass crop_image_url (JSON) or face_image (multipart file).
    is_register is always set to false for this flow.
    """
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        name = ((form.get("name") or "") if isinstance(form.get("name"), str) else "").strip()
        aadhaar = ((form.get("aadhaar_number") or "") if isinstance(form.get("aadhaar_number"), str) else "").strip()
        contact_number = form.get("contact_number")
        contact_number = (contact_number or "").strip() if isinstance(contact_number, str) else None
        emergency_contact_number = form.get("emergency_contact_number")
        emergency_contact_number = (emergency_contact_number or "").strip() if isinstance(emergency_contact_number, str) else None
        is_pilot_val = str(form.get("is_pilot", "false")).lower() in ("true", "1", "on", "yes")
        crop_url = ((form.get("crop_image_url") or "") if isinstance(form.get("crop_image_url"), str) else "").strip()
        face_image = form.get("face_image")
    else:
        body = await request.json()
        name = (body.get("name") or "").strip()
        aadhaar = (body.get("aadhaar_number") or "").strip()
        contact_number = (body.get("contact_number") or "").strip() or None
        emergency_contact_number = (body.get("emergency_contact_number") or "").strip() or None
        is_pilot_val = body.get("is_pilot", False) is True
        crop_url = (body.get("crop_image_url") or "").strip()
        face_image = None

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
    officer_id = current_user.get("id")
    profile_crop_id: Optional[str] = None
    # Prefer crop_id from crop_image_url if provided (scan-result flow).
    if crop_url:
        try:
            parsed = urlparse(crop_url)
            path_parts = [p for p in parsed.path.split("/") if p]
            for i, part in enumerate(path_parts):
                if part == "scan-result" and i + 1 < len(path_parts):
                    profile_crop_id = path_parts[i + 1]
                    break
        except Exception as parse_err:
            logger.warning("Failed to parse crop_image_url for profile crop: %s", parse_err)
            profile_crop_id = None

    # If face_image is provided, store a cropped face as profile image.
    if not profile_crop_id and face_image and hasattr(face_image, "read"):
        img_bytes = await face_image.read()
        face_detected, crop_bytes = face_service.detect_face_and_crop(img_bytes)
        if face_detected and crop_bytes:
            profile_crop_id = str(uuid.uuid4())
            save_crew_crop(profile_crop_id, crop_bytes)

    crew_member_id = face_service.register_user_minimal(
        name=name,
        aadhaar_number=aadhaar,
        contact_number=contact_number,
        emergency_contact_number=emergency_contact_number,
        is_pilot=is_pilot_val,
        registered_by_user_id=officer_id,
        profile_crop_id=profile_crop_id,
    )
    if not crew_member_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A crew member with this Aadhaar number already exists",
        )
    # Optionally attach a face embedding from face_image (file) or crop_image_url.
    embedding: Optional[np.ndarray] = None
    # If we already read face_image above for profile crop, we can't re-read it here.
    # Use crop_url embedding when available; otherwise the officer can re-upload if needed.
    if crop_url and crew_member_id:
        crop_id: Optional[str] = None
        try:
            parsed = urlparse(crop_url)
            path_parts = [p for p in parsed.path.split("/") if p]
            for i, part in enumerate(path_parts):
                if part == "scan-result" and i + 1 < len(path_parts):
                    crop_id = path_parts[i + 1]
                    break
        except Exception as parse_err:
            logger.warning("Failed to parse crop_image_url: %s", parse_err)
            crop_id = None
        if crop_id:
            # Prefer pre-computed embedding from scan-group-photo (no re-detection)
            emb_list = _scan_result_embeddings.get(crop_id) or load_crew_embedding(crop_id)
            if emb_list:
                embedding = np.array(emb_list, dtype=np.float32)
            else:
                png_bytes = _scan_result_crops.get(crop_id) or load_crew_crop(crop_id)
                if not png_bytes and crop_url.startswith(("http://", "https://")):
                    try:
                        resp = await asyncio.to_thread(requests.get, crop_url, timeout=10)
                        if resp.status_code == 200 and resp.content:
                            png_bytes = resp.content
                    except Exception as fetch_err:
                        logger.warning("Failed to fetch crop_image_url: %s", fetch_err)
                if png_bytes:
                    embedding = face_service.get_embedding(png_bytes)
    embedding_added = False
    if embedding is not None:
        if face_service.add_face_embedding(crew_member_id, embedding):
            embedding_added = True
            logger.info("Face embedding added for crew_member_id=%s", crew_member_id)
        else:
            logger.warning("add_face_embedding failed for crew_member_id=%s", crew_member_id)

    crew_member = face_service.get_crew_member_by_id(crew_member_id)
    return {
        "success": True,
        "id": crew_member_id,
        "message": "User registered successfully (is_register=false)",
        "crew_member": crew_member,
        "embedding_added": embedding_added,
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
    face_detected, crop_bytes = face_service.detect_face_and_crop(image_bytes)
    profile_crop_id: Optional[str] = None
    if face_detected and crop_bytes:
        profile_crop_id = str(uuid.uuid4())
        save_crew_crop(profile_crop_id, crop_bytes)

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
        profile_crop_id=profile_crop_id,
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
    Step 2: Verify OTP sent to the crew member's phone.
    With a pending row (photo + OTP flow), creates the crew member.
    With only an unregistered crew row (e.g. minimal officer register), marks that row as registered.
    """
    phone = req.mobile_number.strip()
    if not crud_user.verify_otp(phone, req.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    pending = crud_user.get_pending_crew_by_phone(phone)
    if pending:
        emb = pending["embedding"]
        if isinstance(emb, str):
            emb = json.loads(emb)
        embedding = np.array(emb, dtype=np.float32)
        officer_id = current_user.get("id")
        user_id = face_service.register_user(
            pending["name"],
            embedding,
            aadhaar_number=pending["aadhaar_number"],
            contact_number=pending["phone"],
            emergency_contact_number=pending["emergency_contact_number"],
            is_pilot=pending["is_pilot"],
            registered_by_user_id=officer_id,
            profile_crop_id=pending.get("profile_crop_id"),
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
            "is_register": True,
            "message": "Crew member created successfully"
        }

    unregistered = face_service.get_unregistered_crew_member_for_phone(phone)
    if unregistered:
        if not face_service.promote_crew_member_to_registered(unregistered["id"]):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete crew registration"
            )
        crew = face_service.get_crew_member_by_id(unregistered["id"])
        if not crew:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load crew member"
            )
        return {
            "success": True,
            "id": crew["id"],
            "name": crew["name"],
            "aadhaar_number": crew["aadhaar_number"],
            "contact_number": crew["contact_number"],
            "emergency_contact_number": crew["emergency_contact_number"],
            "is_pilot": crew["is_pilot"],
            "is_register": True,
            "message": "Crew member verified successfully"
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No pending crew registration for this phone. Please submit the form again."
    )


@router.post("/crew-members/resend-otp")
async def resend_crew_otp(
    req: ForgotPasswordRequest,
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """Resend OTP when there is a pending registration row or an unregistered crew member for this phone."""
    phone = req.mobile_number.strip()
    pending = crud_user.get_pending_crew_by_phone(phone)
    unregistered = None if pending else face_service.get_unregistered_crew_member_for_phone(phone)
    if not pending and not unregistered:
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
        png_bytes = load_crew_crop(crop_id)
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
            annotated_image_url = resolve_image_url(url_path, str(request.base_url))

    faces: List[CrewFaceScanResult] = []
    request_base = str(request.base_url)
    for f in faces_payload:
        crew_member_data = f.get("crew_member")
        crew_member_obj = None
        if crew_member_data:
            crew_member_obj = CrewMemberResponse(**crew_member_data)

        crop_id: Optional[str] = None
        crop_image_url: Optional[str] = None
        bbox = f.get("bbox")
        if bbox and len(bbox) == 4:
            crop_bytes = face_service.crop_face_from_image(image_bytes, bbox)
            if crop_bytes:
                crop_id = str(uuid.uuid4())
                _scan_result_crops[crop_id] = crop_bytes
                save_crew_crop(crop_id, crop_bytes)
                emb = f.get("embedding")
                if emb is not None:
                    _scan_result_embeddings[crop_id] = emb
                    save_crew_embedding(crop_id, emb)
                path = request.url_for("get_scan_result_crop", crop_id=crop_id)
                path_str = str(path)
                crop_image_url = resolve_image_url(path_str, request_base)

        faces.append(
            CrewFaceScanResult(
                det_score=f.get("det_score", 0.0),
                distance=f.get("distance"),
                is_match=bool(f.get("is_match")),
                crew_member=crew_member_obj,
                crop_id=crop_id,
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
