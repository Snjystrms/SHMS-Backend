from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token

router = APIRouter()

class LoginRequestForm:
    def __init__(
        self,
        email_or_phone: str = Form(..., description="Email or Phone Number"),
        password: str = Form(...),
        grant_type: str = Form(None, pattern="password"),
        scope: str = Form(""),
        client_id: str = Form(None),
        client_secret: str = Form(None),
    ):
        self.email_or_phone = email_or_phone
        self.password = password
        self.grant_type = grant_type
        self.scope = scope
        self.client_id = client_id
        self.client_secret = client_secret

@router.post("/login", response_model=Token)
async def login(form_data: LoginRequestForm = Depends()):
    """Admin login endpoint."""
    user = crud_user.get_user_by_identifier(form_data.email_or_phone)
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
