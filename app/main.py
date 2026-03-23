from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1.router import api_router
from app.api.v1.endpoints import auction_ws
from app.core.config import settings
from app.utils import get_local_ip
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
)
from fastapi import HTTPException
from pathlib import Path

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Resolve and ensure the uploads directory exists before mounting (important for Render)
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Serve uploaded files (boat documents) from /uploads/...
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Register exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# Set all CORS enabled origins
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
    print(f"🚀 {settings.PROJECT_NAME} IS RUNNING!")
    print("🔗 Local link:    http://127.0.0.1:8000")
    print(f"👥 Network link:  http://{local_ip}:8000")
    print(f"📜 API Docs:      http://{local_ip}:8000/docs")
    print("="*50 + "\n")
    
    if local_ip == "127.0.0.1":
        print("⚠️  Warning: Could not detect local network IP.")
    else:
        print(f"💡 Share 'http://{local_ip}:8000' with your colleagues.")

app.include_router(api_router, prefix=settings.API_V1_STR)
# Also expose WebSockets without the `/api/v1` prefix for convenience (mobile/Expo dev).
app.include_router(auction_ws.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def health_check():
    return {"status": "SHMS Backend is running"}