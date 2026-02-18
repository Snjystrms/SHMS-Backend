from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from app.core import security
from app.core.config import settings
from app.services import user_service as crud_user
from app.schemas.token import Token
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest, VerifyResetOtpRequest
from app.utils.otp_helpers import send_otp_for_phone

router = APIRouter()

OFFICER_NOT_FOUND_DETAIL = "No port officer found with this mobile number"


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
    stored = user.get("password")
    if stored and not stored.startswith("$2b$") and not stored.startswith("$2a$"):
        hashed = security.get_password_hash(form_data.password)
        crud_user.update_user_password(user["id"], hashed)

    return _token_response(user)


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Send OTP to port officer's mobile. Officer-only."""
    return send_otp_for_phone(
        req.mobile_number.strip(),
        crud_user.get_officer_by_phone,
        OFFICER_NOT_FOUND_DETAIL,
    )


@router.post("/verify-reset-otp")
async def verify_reset_otp(req: VerifyResetOtpRequest):
    """Verify OTP for port officer password reset. Officer-only. Returns reset_token for reset-password."""
    phone = req.mobile_number.strip()
    officer = crud_user.get_officer_by_phone(phone)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=OFFICER_NOT_FOUND_DETAIL,
        )
    if not crud_user.verify_otp(phone, req.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )
    reset_token = security.create_password_reset_token(officer["id"])
    return {"message": "OTP verified. Proceed to reset password.", "reset_token": reset_token}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Set new password using reset_token from verify-reset-otp. Officer-only."""
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Minimum 6 characters required")
    user_id = security.decode_password_reset_token(req.reset_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token. Please verify OTP again.",
        )
    hashed = security.get_password_hash(req.new_password)
    crud_user.update_user_password(user_id, hashed)
    return {"message": "Password reset successfully"}
