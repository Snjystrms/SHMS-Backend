from fastapi import APIRouter
from app.api.v1.endpoints import auth, admin, crew

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])

api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(crew.router, tags=["crew"])
