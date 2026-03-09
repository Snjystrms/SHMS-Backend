from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder

from app.services import auction_service

router = APIRouter()

# In-memory connection store:
# auction_id -> list[WebSocket]
active_auction_connections: Dict[str, List[WebSocket]] = {}


@router.websocket("/ws/auctions/{auction_id}")
async def auction_live(websocket: WebSocket, auction_id: str):
    """
    WebSocket endpoint for live auction updates (bids).

    - Validates that the auction exists before accepting the connection.
    - On connect, sends an initial snapshot of the auction and its bids.
    - Keeps the connection open, ignoring client messages except for basic pings.
    """
    # Validate auction existence before accepting
    auction = auction_service.get_auction_by_id(auction_id)
    if not auction:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    connections = active_auction_connections.setdefault(auction_id, [])
    connections.append(websocket)

    # Send initial snapshot: auction details + current bids (ensure JSON-serializable)
    bids = auction_service.list_bids_for_auction(auction_id)
    payload = {
        "type": "initial_state",
        "auction": jsonable_encoder(auction),
        "bids": jsonable_encoder(bids),
    }
    try:
        await websocket.send_json(payload)
    except Exception as e:
        print("Error sending initial_state over WebSocket:", repr(e))
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            active_auction_connections.pop(auction_id, None)
        return

    try:
        # Keep the connection open; ignore client messages (basic ping handling).
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            active_auction_connections.pop(auction_id, None)

