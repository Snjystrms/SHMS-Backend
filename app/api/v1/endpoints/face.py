from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.services import face_service
from app.core.config import settings


router = APIRouter()

@router.post("/identify")
async def identify_face(file: UploadFile = File(...)):
    image_bytes = await file.read()
    embedding = face_service.get_embedding(image_bytes)

    if embedding is None:
        return {"success": False, "message": "No face detected"}

    user_id, username, distance = face_service.find_match(embedding)

    if user_id and distance < settings.FACE_MATCH_THRESHOLD:

        return {
            "success": True,
            "matched": True,
            "user_id": user_id,
            "username": username,
            "confidence": round(1 - distance, 2)
        }

    return {
        "success": True,
        "matched": False,
        "message": "User not found"
    }

@router.post("/register")
async def register_face(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    image_bytes = await file.read()
    embedding = face_service.get_embedding(image_bytes)

    if embedding is None:
        return {
            "success": False,
            "message": "Invalid image or no face detected"
        }
    
    # 🔍 CHECK IF FACE ALREADY EXISTS
    existing_user_id, existing_username, distance = face_service.find_match(embedding)

    if distance is not None and distance < settings.FACE_DUPLICATE_THRESHOLD:

        return {
            "success": False,
            "message": "Face already registered",
            "existing_user_id": existing_user_id,
            "existing_username": existing_username,
            "similarity": round(1 - distance, 2)
        }

    # ✅ REGISTER NEW USER
    user_id = face_service.register_user(name, embedding)

    return {
        "success": True,
        "user_id": user_id,
        "message": "User registered successfully"
    }

@router.post("/add-photo")
async def add_photo(
    file: UploadFile = File(...),
    user_id: str = Form(None),
    name: str = Form(None)
):
    """Add an additional photo to an existing user (by user_id or name)"""
    
    if not user_id and not name:
        return {
            "success": False,
            "message": "Either user_id or name is required"
        }
    
    image_bytes = await file.read()
    embedding = face_service.get_embedding(image_bytes)

    if embedding is None:
        return {
            "success": False,
            "message": "Invalid image or no face detected"
        }
    
    # If name is provided, get the user_id
    if name and not user_id:
        user_id = face_service.get_user_id_by_name(name)
        if not user_id:
            return {
                "success": False,
                "message": f"User '{name}' not found"
            }
    
    # Add embedding for the existing user
    result = face_service.add_face_embedding(user_id, embedding)

    if result:
        return {
            "success": True,
            "message": "Photo added successfully",
            "user_id": user_id
        }
    else:
        return {
            "success": False,
            "message": "Failed to add photo"
        }
