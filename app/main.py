from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from app.face_service import get_embedding, find_match, register_user
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from app.auth import create_access_token, verify_password, get_password_hash, get_admin_user
from app.user_service import get_user_by_identifier, update_user_password, get_role_id_by_name, create_user
from app.models import UserCreate
from app.utils import get_local_ip
from datetime import timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow all origins (DEV only)
    allow_credentials=True,
    allow_methods=["*"],        # GET, POST, PUT, DELETE
    allow_headers=["*"],        # Content-Type, Authorization, etc.
)

@app.on_event("startup")
async def startup_event():
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print(f"🚀 SERVER IS RUNNING!")
    print(f"🔗 Local link:    http://127.0.0.1:8000")
    print(f"👥 Network link:  http://{local_ip}:8000")
    print(f"📜 API Docs:      http://{local_ip}:8000/docs")
    print("="*50 + "\n")
    
    if local_ip == "127.0.0.1":
        print("⚠️  Warning: Could not detect local network IP.")
    else:
        print(f"💡 Share 'http://{local_ip}:8000' with your colleagues.")

@app.post("/identify")
async def identify_face(file: UploadFile = File(...)):
    image_bytes = await file.read()
    embedding = get_embedding(image_bytes)

    if embedding is None:
        return {"success": False, "message": "No face detected"}

    user_id, username, distance = find_match(embedding)

    if user_id and distance < 0.4:
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

@app.post("/register")
async def register_face(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    image_bytes = await file.read()
    embedding = get_embedding(image_bytes)

    if embedding is None:
        return {
            "success": False,
            "message": "Invalid image or no face detected"
        }
    
    # 🔍 CHECK IF FACE ALREADY EXISTS
    existing_user_id, existing_username, distance = find_match(embedding)

    if distance is not None and distance < 0.30:
        return {
            "success": False,
            "message": "Face already registered",
            "existing_user_id": existing_user_id,
            "existing_username": existing_username,
            "similarity": round(1 - distance, 2)
        }

    # ✅ REGISTER NEW USER
    user_id = register_user(name, embedding)

    return {
        "success": True,
        "user_id": user_id,
        "message": "User registered successfully"
    }


@app.post("/add-photo")
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
    embedding = get_embedding(image_bytes)

    if embedding is None:
        return {
            "success": False,
            "message": "Invalid image or no face detected"
        }
    
    from app.face_service import add_face_embedding, get_user_id_by_name
    
    # If name is provided, get the user_id
    if name and not user_id:
        user_id = get_user_id_by_name(name)
        if not user_id:
            return {
                "success": False,
                "message": f"User '{name}' not found"
            }
    
    # Add embedding for the existing user
    result = add_face_embedding(user_id, embedding)

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

@app.post("/login")
async def login(form_data: LoginRequestForm = Depends()):
    """Admin login endpoint."""
    user = get_user_by_identifier(form_data.email_or_phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/phone",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Optional: Automatically hash plain text password on first login
    if not user["password"].startswith("$2b$") and not user["password"].startswith("$2a$"):
        hashed = get_password_hash(form_data.password)
        update_user_password(user["id"], hashed)

    access_token_expires = timedelta(minutes=60 * 24)
    access_token = create_access_token(
        data={"sub": user["id"], "role": user["role"]},
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

@app.post("/admin/create-officer", status_code=status.HTTP_201_CREATED)
async def create_officer_account(
    user_data: UserCreate,
    current_admin: dict = Depends(get_admin_user)
):
    """Admin-only endpoint to create an officer account."""
    # Check if user already exists
    existing_user = get_user_by_identifier(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Get officer role ID
    role_id = get_role_id_by_name("officer")
    if not role_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Officer role not found in database"
        )
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    new_user_dict = user_data.dict()
    new_user_dict["password"] = hashed_password
    
    user_id = create_user(new_user_dict, role_id)
    
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
