from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    admin,
    crew,
    boat_owners,
    port_officer,
    auction,
    auction_ws,
)

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(boat_owners.router, prefix="/boat-owners", tags=["boat-owners"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(crew.router, tags=["crew"])
api_router.include_router(port_officer.router, prefix="/port-officer", tags=["port-officer"])
api_router.include_router(auction.router, tags=["auction"])
api_router.include_router(auction_ws.router, tags=["auction-ws"])
