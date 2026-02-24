from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends, Body
from app.services import face_service
from app.core.config import settings
from app.api import deps
from app.schemas.crew import CrewMemberResponse, CrewMemberUpdate


router = APIRouter()

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

@router.post("/crew-members", status_code=status.HTTP_201_CREATED)
async def create_crew_member(
    name: str = Form(...),
    aadhaar_number: str = Form(None),
    contact_number: str = Form(None),
    emergency_contact_number: str = Form(None),
    is_pilot: str = Form("false"),
    file: UploadFile = File(...),
    current_user: dict = Depends(deps.get_admin_or_officer_user)
):
    """Create a new crew member with an initial face photo."""
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

    is_pilot_val = (is_pilot or "").strip().lower() in ("true", "1", "on", "yes")
    user_id = face_service.register_user(name, embedding, aadhaar_number, contact_number, emergency_contact_number, is_pilot=is_pilot_val)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register crew member"
        )

    return {
        "success": True,
        "id": user_id,
        "name": name,
        "aadhaar_number": aadhaar_number,
        "contact_number": contact_number,
        "emergency_contact_number": emergency_contact_number,
        "is_pilot": is_pilot_val,
        "message": "Crew member created successfully"
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
