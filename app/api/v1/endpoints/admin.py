from fastapi import APIRouter, Depends, HTTPException, status
from app.services import user_service as crud_user
from app.schemas.user import UserCreate, UserUpdate
from app.api import deps
from app.core import security

router = APIRouter()

@router.post("/create-officer", status_code=status.HTTP_201_CREATED)
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
    
    user_id = crud_user.create_user(new_user_dict, role_id)
    
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
