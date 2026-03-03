from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# In-memory connection store:
# auction_id -> list[WebSocket]
active_auction_connections: Dict[str, List[WebSocket]] = {}


@router.websocket("/ws/auctions/{auction_id}")
async def auction_live(websocket: WebSocket, auction_id: str):
    """WebSocket endpoint for live auction updates (bids)."""
    await websocket.accept()

    connections = active_auction_connections.setdefault(auction_id, [])
    connections.append(websocket)

    try:
        # Keep the connection open; ignoring client messages for now.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            active_auction_connections.pop(auction_id, None)

