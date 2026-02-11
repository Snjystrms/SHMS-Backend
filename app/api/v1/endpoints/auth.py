from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token
from app.schemas.user import UserCreate

router = APIRouter()

class LoginRequestForm:
    def __init__(
        self,
        mobile_number: str = Form(..., description="Email or Phone Number"),
        password: str = Form(...),
        grant_type: str = Form(None, pattern="password"),
        scope: str = Form(""),
        client_id: str = Form(None),
        client_secret: str = Form(None),
    ):
        self.mobile_number = mobile_number
        self.password = password
        self.grant_type = grant_type
        self.scope = scope
        self.client_id = client_id
        self.client_secret = client_secret

@router.post("/login", response_model=Token)
async def login(form_data: LoginRequestForm = Depends()):
    """Admin login endpoint."""
    user = crud_user.get_user_by_identifier(form_data.mobile_number)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/phone",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not security.verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Optional: Automatically hash plain text password on first login
    if not user["password"].startswith("$2b$") and not user["password"].startswith("$2a$"):
        hashed = security.get_password_hash(form_data.password)
        crud_user.update_user_password(user["id"], hashed)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user["id"],
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    }

@router.post("/boat-owners/register", status_code=status.HTTP_201_CREATED)
async def register_boat_owner(user_data: UserCreate):
    """
    Public registration endpoint for boat owners.
    """
    # Check if user already exists
    existing_user = crud_user.get_user_by_identifier(user_data.email)
    if not existing_user:
        existing_user = crud_user.get_user_by_identifier(user_data.phone)
        
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone already exists"
        )
    
    # Get boat_owner role ID
    role_id = crud_user.get_role_id_by_name("boat_owner")
    if not role_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Boat owner role not found in database"
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
            detail="Failed to register boat owner"
        )
    
    return {
        "success": True,
        "user_id": user_id,
        "message": "Boat owner registered successfully"
    }
