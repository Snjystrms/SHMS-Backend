"""Boat owner registration, OTP login, and boat CRUD (own boats only)."""
from datetime import timedelta
from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token
from app.schemas.user import BoatOwnerCreate, BoatCreate, BoatUpdate, ForgotPasswordRequest, BoatOwnerVerifyOtpRequest
from app.api import deps
from app.utils.otp_helpers import get_sms, send_otp_for_phone
from app.utils.uploads import ALLOWED_BOAT_DOCUMENT_TYPES, save_boat_document

router = APIRouter()

BOAT_OWNER_NOT_FOUND_DETAIL = "No boat owner found with this mobile number"


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
    existing_boat_owner = crud_user.get_boat_owner_by_phone(phone)
    if existing_boat_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A boat owner with this mobile number already exists",
        )
    if not crud_user.create_temp_user(user_data.name, phone):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save registration",
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
        "message": "OTP sent to your mobile. Verify to complete registration.",
        "masked_mobile": crud_user.mask_mobile(phone),
        "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES,
    }


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
    if not crud_user.verify_otp(phone, req.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    temp = crud_user.get_temp_user_by_phone(phone)
    if temp:
        role_id = crud_user.get_role_id_by_name("boat_owner")
        if not role_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Boat owner role not found",
            )
        new_user_dict = {"name": temp["name"], "phone": phone}
        user_id = crud_user.create_user(new_user_dict, role_id)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete registration",
            )
        crud_user.delete_temp_user_by_phone(phone)
        user = crud_user.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User data not found")
        return _token_response(user)
    owner = crud_user.get_boat_owner_by_phone(phone)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=BOAT_OWNER_NOT_FOUND_DETAIL,
        )
    user = crud_user.get_user_by_id(owner["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User data not found")
    return _token_response(user)


# ----- Boat CRUD (owner's own boats only) -----
@router.get("/boats")
async def list_my_boats(current_user: dict = Depends(deps.get_boat_owner_user)):
    """List boats belonging to the authenticated boat owner."""
    boats = crud_user.get_boats_by_owner_id(current_user["id"])
    return {"success": True, "boats": boats}


@router.post("/boats", status_code=status.HTTP_201_CREATED)
async def create_boat(
    boat_number: str = Form(..., description="Boat registration number"),
    document: UploadFile = File(None, description="Boat document (PDF or image: JPEG/PNG), optional"),
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Add a boat for the authenticated boat owner. Optionally upload a document (PDF or image)."""
    data = {"boat_number": boat_number.strip(), "boat_document": None, "boat_document_content_type": None, "boat_document_filename": None}
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
    return {"success": True, "boat": boat}


@router.put("/boats/{boat_id}")
async def update_my_boat(
    boat_id: str,
    boat_number: str = Form(None, description="Boat registration number (optional)"),
    document: UploadFile = File(None, description="Replace boat document with PDF or image (optional)"),
    current_user: dict = Depends(deps.get_boat_owner_user),
):
    """Update a boat; must belong to the authenticated boat owner. Optionally upload a new document."""
    boat = crud_user.get_boat_by_id(boat_id)
    if not boat or boat["boat_owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    update_dict = {}
    if boat_number is not None and boat_number.strip():
        update_dict["boat_number"] = boat_number.strip()
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
