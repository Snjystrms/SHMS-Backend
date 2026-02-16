from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token
from app.schemas.user import UserCreate, ForgotPasswordRequest, ResendOtpRequest, ResetPasswordRequest
from app.utils.sms import get_sms_provider

router = APIRouter()


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

class LoginRequestForm:
    def __init__(
        self,
        mobile_number: str = Form(None, description="Mobile Number"),
        username: str = Form(None, description="Mobile Number (OAuth2 compatibility)"),
        password: str = Form(...),
        grant_type: str = Form(None, pattern="password"),
        scope: str = Form(""),
        client_id: str = Form(None),
        client_secret: str = Form(None),
    ):
        # Accept either mobile_number or username (for OAuth2 compatibility)
        self.mobile_number = mobile_number or username
        if not self.mobile_number:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either mobile_number or username must be provided"
            )
        self.password = password
        self.grant_type = grant_type
        self.scope = scope
        self.client_id = client_id
        self.client_secret = client_secret

@router.post("/login", response_model=Token)
async def login(form_data: LoginRequestForm = Depends()):
    """Login endpoint - accepts mobile number only."""
    user = crud_user.get_user_by_identifier(form_data.mobile_number)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number",
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


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Send OTP to port officer's mobile. Officer-only."""
    phone = req.mobile_number.strip()
    officer = crud_user.get_officer_by_phone(phone)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No port officer found with this mobile number",
        )
    otp, ok = crud_user.create_and_store_otp(phone, settings.SMS_OTP_EXPIRE_MINUTES)
    if not ok or not otp:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate OTP")
    sms = _get_sms()
    if not sms.send_otp(phone, otp):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP")
    return {"masked_mobile": crud_user.mask_mobile(phone), "expires_in_minutes": settings.SMS_OTP_EXPIRE_MINUTES}


@router.post("/resend-otp")
async def resend_otp(req: ResendOtpRequest):
    """Resend OTP to port officer's mobile."""
    return await forgot_password(ForgotPasswordRequest(mobile_number=req.mobile_number))


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Verify OTP and set new password. Officer-only."""
    phone = req.mobile_number.strip()
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Minimum 6 characters required")
    officer = crud_user.get_officer_by_phone(phone)
    if not officer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No port officer found with this mobile number")
    if not crud_user.verify_otp(phone, req.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    hashed = security.get_password_hash(req.new_password)
    crud_user.update_user_password(officer["id"], hashed)
    return {"message": "Password reset successfully"}
