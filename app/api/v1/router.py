from fastapi import APIRouter
from app.api.v1.endpoints import auth, face, admin

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(face.router, tags=["face"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
