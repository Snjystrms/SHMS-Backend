import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi.encoders import jsonable_encoder
from fastapi.websockets import WebSocketState

from app.db.session import get_db_connection
from app.schemas.auction import AuctionStatus
from app.api.v1.endpoints.auction_ws import active_auction_connections

# Current time in IST for status checks (start_time/end_time treated as IST).
# PostgreSQL: NOW() in UTC + 5h30m approximates IST for comparison.
_NOW_IST_SQL = "NOW() + INTERVAL '5 hours 30 minutes'"
_IST = timezone(timedelta(hours=5, minutes=30))


def _normalize_to_ist(dt: datetime) -> datetime:
    """
    Normalize datetimes to IST for consistent comparisons/storage.

    - If timezone-aware: convert to IST.
    - If timezone-naive: treat as already-IST (common for UI date-time pickers).
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=_IST)
    return dt.astimezone(_IST)


def _auction_from_row(row) -> Dict[str, Any]:
    """Map auctions table row to dict. Times normalized to IST for consistent API response."""
    start = row[5]
    end = row[6]
    return {
        "id": str(row[0]),
        "seller_id": str(row[1]),
        "fish_name": row[2],
        "initial_price": float(row[3]),
        "current_price": float(row[4]),
        "start_time": _normalize_to_ist(start) if start else None,
        "end_time": _normalize_to_ist(end) if end else None,
        "status": row[7],
        "winner_id": str(row[8]) if row[8] else None,
        "bidding_request_id": str(row[9]) if len(row) > 9 and row[9] else None,
        "auction_type": row[10] if len(row) > 10 else "open_box",
        "movement_id": str(row[11]) if len(row) > 11 and row[11] else None,
    }


def _validate_movement_for_boat_owner(
    cur, movement_id: str, boat_owner_id: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate movement exists, is departure/arrival, and boat belongs to boat_owner.
    Returns (boat_owner_id as seller_id, None) or (None, error).
    """
    cur.execute(
        """
        SELECT m.id, m.boat_id, m.movement_type
        FROM boat_movements m
        JOIN boats b ON b.id = m.boat_id AND b.deleted_at IS NULL
        WHERE m.id = %s AND b.boat_owner_id = %s
          AND m.movement_type IN ('departure', 'arrival')
        """,
        (movement_id, boat_owner_id),
    )
    row = cur.fetchone()
    if not row:
        return None, "Movement not found or boat does not belong to you"
    return boat_owner_id, None


def _validate_bidding_request(
    cur, bidding_request_id: str, caller_id: str, caller_role: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate bidding_request exists and is approved.
    For boat_owner: boat_owner_id must match caller_id. Returns (seller_id, None) or (None, error).
    For agent: agent_id must match caller_id. Returns (boat_owner_id as seller_id, None) or (None, error).
    """
    cur.execute(
        """
        SELECT id, status, boat_owner_id, agent_id FROM bidding_requests WHERE id = %s
        """,
        (bidding_request_id,),
    )
    row = cur.fetchone()
    if not row:
        return None, "Bidding request not found"
    if row[1] != "approved":
        return None, "Bidding request must be approved"
    boat_owner_id = str(row[2]) if row[2] else None
    agent_id = str(row[3]) if row[3] else None
    if caller_role == "boat_owner":
        if boat_owner_id != str(caller_id):
            return None, "Invalid or unauthorized bidding request"
        return caller_id, None
    if caller_role == "agent":
        if agent_id != str(caller_id):
            return None, "Invalid or unauthorized bidding request"
        return boat_owner_id, None
    return None, "Invalid role"


def create_auction(
    caller_id: str,
    caller_role: str,
    fish_name: str,
    initial_price: float,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    movement_id: Optional[str] = None,
    bidding_request_id: Optional[str] = None,
    auction_type: str = "open_box",
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Insert new auction into DB.
    - Boat owner self auction: movement_id required, validates boat belongs to owner.
    - Agent/boat owner from approved request: bidding_request_id required.
    - end_time is optional; when not provided, defaults to start_time + 24 hours.
    """
    fish_name = (fish_name or "").strip()
    if not fish_name:
        return None, "fish_name is required"
    if initial_price is None or initial_price <= 0:
        return None, "initial_price must be > 0"

    start_time_ist = _normalize_to_ist(start_time)
    if end_time is not None:
        end_time_ist = _normalize_to_ist(end_time)
        if end_time_ist <= start_time_ist:
            return None, "end_time must be after start_time"
    else:
        end_time_ist = start_time_ist + timedelta(hours=24)

    has_movement = bool(movement_id and str(movement_id).strip())
    has_request = bool(bidding_request_id and str(bidding_request_id).strip())
    if has_movement and has_request:
        return None, "Provide either movement_id or bidding_request_id, not both"
    if not has_movement and not has_request:
        return None, "Provide either movement_id or bidding_request_id"

    auction_id = str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if has_movement:
            if caller_role != "boat_owner":
                return None, "Only boat owner can create self auction with movement_id"
            seller_id, err = _validate_movement_for_boat_owner(
                cur, movement_id.strip(), caller_id
            )
            if err:
                return None, err
            store_movement_id = movement_id.strip()
            store_bidding_request_id = None
        else:
            seller_id, err = _validate_bidding_request(
                cur, bidding_request_id.strip(), caller_id, caller_role
            )
            if err:
                return None, err
            store_movement_id = None
            store_bidding_request_id = bidding_request_id.strip()

        cur.execute(
            """
            INSERT INTO auctions (
                id, seller_id, fish_name, initial_price, current_price,
                start_time, end_time, status, bidding_request_id, auction_type, movement_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'scheduled', %s, %s, %s)
            """,
            (
                auction_id,
                seller_id,
                fish_name,
                initial_price,
                initial_price,
                start_time_ist,
                end_time_ist,
                store_bidding_request_id,
                auction_type,
                store_movement_id,
            ),
        )
        conn.commit()
        return {
            "id": auction_id,
            "seller_id": seller_id,
            "fish_name": fish_name,
            "initial_price": initial_price,
            "current_price": initial_price,
            "start_time": start_time_ist,
            "end_time": end_time_ist,
            "status": "scheduled",
            "winner_id": None,
            "bidding_request_id": store_bidding_request_id,
            "movement_id": store_movement_id,
            "auction_type": auction_type,
        }, None
    except Exception as e:
        conn.rollback()
        err = f"Failed to create auction in DB: {e}"
        print(err)
        return None, err
    finally:
        cur.close()
        conn.close()


def get_auction_by_id(auction_id: str) -> Optional[Dict[str, Any]]:
    """Fetch one auction and lazily update its status based on current IST time."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            UPDATE auctions
            SET status = CASE
                    WHEN {_NOW_IST_SQL} >= end_time THEN 'completed'
                    WHEN {_NOW_IST_SQL} >= start_time THEN 'active'
                    ELSE status
                END,
                updated_at = NOW()
            WHERE id = %s
            """,
            (auction_id,),
        )
        conn.commit()

        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price,
                   start_time, end_time, status, winner_id, bidding_request_id, auction_type, movement_id
            FROM auctions
            WHERE id = %s
            """,
            (auction_id,),
        )
        row = cur.fetchone()
        return _auction_from_row(row) if row else None
    except Exception as e:
        conn.rollback()
        print(f"Error fetching auction by id: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def list_auctions() -> List[Dict[str, Any]]:
    """Return all auctions, updating their status based on current IST time."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            UPDATE auctions
            SET status = CASE
                    WHEN {_NOW_IST_SQL} >= end_time THEN 'completed'
                    WHEN {_NOW_IST_SQL} >= start_time THEN 'active'
                    ELSE status
                END,
                updated_at = NOW()
            WHERE status IN ('scheduled', 'active')
            """
        )
        conn.commit()

        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price,
                   start_time, end_time, status, winner_id, bidding_request_id, auction_type, movement_id
            FROM auctions
            ORDER BY created_at DESC
            """,
        )
        rows = cur.fetchall()
        return [_auction_from_row(r) for r in rows]
    except Exception as e:
        conn.rollback()
        print(f"Error listing auctions: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def _update_auction_status(conn, auction_id: str, new_status: AuctionStatus) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE auctions SET status = %s WHERE id = %s",
        (new_status, auction_id),
    )


def update_auction(
    auction_id: str,
    seller_id: str,
    fish_name: Optional[str],
    start_time: Optional[datetime],
    bidding_request_id: Optional[str] = None,
    movement_id: Optional[str] = None,
    auction_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update editable fields of an auction owned by seller_id."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch existing auction to validate ownership and state
        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price,
                   start_time, end_time, status, winner_id, bidding_request_id, auction_type, movement_id
            FROM auctions
            WHERE id = %s AND seller_id = %s
            """,
            (auction_id, seller_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        auction = _auction_from_row(row)

        # Do not allow editing completed auctions
        if auction["status"] == "completed":
            return None

        new_fish_name = fish_name.strip() if fish_name is not None else auction["fish_name"]
        if not new_fish_name:
            return None

        existing_start = auction["start_time"]
        existing_end = auction["end_time"]
        new_start_time = _normalize_to_ist(start_time) if start_time is not None else _normalize_to_ist(existing_start)

        if existing_end and new_start_time >= _normalize_to_ist(existing_end):
            return None

        if bidding_request_id is not None:
            _, err = _validate_bidding_request(
                cur, bidding_request_id, seller_id, "boat_owner"
            )
            if err:
                return None

        if movement_id is not None:
            _, err = _validate_movement_for_boat_owner(cur, movement_id, seller_id)
            if err:
                return None

        new_bidding_request_id = bidding_request_id if bidding_request_id is not None else auction.get("bidding_request_id")
        new_movement_id = movement_id if movement_id is not None else auction.get("movement_id")
        new_auction_type = auction_type if auction_type is not None else auction.get("auction_type", "open_box")
        cur.execute(
            """
            UPDATE auctions
            SET fish_name = %s,
                start_time = %s,
                bidding_request_id = %s,
                movement_id = %s,
                auction_type = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (new_fish_name, new_start_time, new_bidding_request_id, new_movement_id, new_auction_type, auction_id),
        )
        conn.commit()

        auction["fish_name"] = new_fish_name
        auction["start_time"] = new_start_time
        auction["bidding_request_id"] = new_bidding_request_id
        auction["movement_id"] = new_movement_id
        auction["auction_type"] = new_auction_type
        return auction
    except Exception as e:
        conn.rollback()
        print(f"Error updating auction: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def delete_auction(auction_id: str, seller_id: str) -> bool:
    """Delete an auction owned by seller_id (not allowed if completed)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE FROM auctions
            WHERE id = %s AND seller_id = %s AND status != 'completed'
            """,
            (auction_id, seller_id),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error deleting auction: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def end_auction(auction_id: str, seller_id: str) -> Optional[Dict[str, Any]]:
    """
    Manually end an auction:
    - Only the seller can end it.
    - Sets status to 'completed'.
    - Sets winner_id to highest bidder (if any).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Ensure auction exists and belongs to seller
        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price,
                   start_time, end_time, status, winner_id, bidding_request_id, auction_type, movement_id
            FROM auctions
            WHERE id = %s AND seller_id = %s
            """,
            (auction_id, seller_id),
        )
        row = cur.fetchone()
        if not row:
            return None

        auction = _auction_from_row(row)
        if auction["status"] == "completed":
            return auction

        # Find highest bid (if any)
        cur.execute(
            """
            SELECT bidder_id, amount
            FROM bids
            WHERE auction_id = %s
            ORDER BY amount DESC, created_at ASC
            LIMIT 1
            """,
            (auction_id,),
        )
        bid_row = cur.fetchone()
        winner_id = bid_row[0] if bid_row else None

        cur.execute(
            """
            UPDATE auctions
            SET status = 'completed',
                winner_id = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (winner_id, auction_id),
        )
        conn.commit()

        auction["status"] = "completed"
        auction["winner_id"] = winner_id
        return auction
    except Exception as e:
        conn.rollback()
        print(f"Error ending auction: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def list_bids_for_auction(auction_id: str) -> List[Dict[str, Any]]:
    """Return all bids for a specific auction, ordered by amount DESC then created_at ASC.

    Includes bidder_name joined from users table for display in clients.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                b.id,
                b.auction_id,
                b.bidder_id,
                b.amount,
                b.quantity,
                b.created_at,
                u.name AS bidder_name
            FROM bids AS b
            JOIN users AS u ON u.id = b.bidder_id
            WHERE b.auction_id = %s
            ORDER BY b.amount DESC, b.created_at ASC
            """,
            (auction_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "auction_id": str(r[1]),
                "bidder_id": str(r[2]),
                "amount": float(r[3]),
                "quantity": float(r[4]) if r[4] is not None else 1.0,
                "created_at": r[5],
                "bidder_name": r[6],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error listing bids for auction {auction_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def create_bid(
    auction_id: str, bidder_id: str, amount: float, quantity: float
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Create a bid and update auction.current_price in a transaction.
    Returns (bid_dict, None) on success, (None, error_message) on failure.
    Uses same IST-based time window as list/get auction.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price,
                   start_time, end_time, status, winner_id, bidding_request_id, auction_type, movement_id
            FROM auctions
            WHERE id = %s
            FOR UPDATE
            """,
            (auction_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, "Auction not found"

        auction = _auction_from_row(row)

        # Only allow bids on scheduled/active auctions
        if auction["status"] not in ("scheduled", "active"):
            return None, f"Auction is not open for bidding (status: {auction['status']})"

        # Use same IST-based "now" as list/get so bidding is allowed when auction shows active
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        if now_ist < auction["start_time"]:
            return None, "Auction has not started yet"
        if now_ist > auction["end_time"]:
            return None, "Auction has ended"

        current_price = float(auction["current_price"])
        if amount <= current_price:
            return None, f"Bid amount must be greater than current price ({current_price})"

        # Transition scheduled -> active when first bid comes in after start_time
        new_status: AuctionStatus = auction["status"]
        if new_status == "scheduled" and now_ist >= auction["start_time"]:
            new_status = "active"

        bid_id = str(uuid.uuid4())
        created_at = now_utc

        cur.execute(
            """
            INSERT INTO bids (id, auction_id, bidder_id, amount, quantity, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (bid_id, auction_id, bidder_id, amount, quantity, created_at),
        )
        cur.execute(
            """
            UPDATE auctions
            SET current_price = %s, status = %s
            WHERE id = %s
            """,
            (amount, new_status, auction_id),
        )
        conn.commit()

        # Fetch bidder name for richer responses
        bidder_name: Optional[str] = None
        try:
            cur.execute(
                "SELECT name FROM users WHERE id = %s",
                (bidder_id,),
            )
            row = cur.fetchone()
            if row:
                bidder_name = row[0]
        except Exception as e:
            # Log but don't fail the whole bid if name lookup fails
            print(f"Error fetching bidder name for {bidder_id}: {e}")

        return {
            "id": bid_id,
            "auction_id": auction_id,
            "bidder_id": bidder_id,
            "amount": amount,
            "quantity": quantity,
            "created_at": created_at,
            "bidder_name": bidder_name,
        }, None
    except Exception as e:
        conn.rollback()
        print(f"Error creating bid: {e}")
        return None, "Failed to place bid"
    finally:
        cur.close()
        conn.close()


async def broadcast_bid(auction_id: str, bid: Dict[str, Any]) -> None:
    """
    Send a bid update to all clients connected to this auction's WebSocket.

    Message format (JSON):
    {
        "type": "new_bid",
        "auction_id": "<auction UUID>",
        "amount": <float>,
        "bidder_id": "<user UUID>",
        "created_at": "<ISO-8601 UTC timestamp>",
        "current_price": <float>,
        "status": "<scheduled|active|completed|cancelled>"
    }
    """
    # Send full state on each bid so all clients can render complete bid history.
    auction = get_auction_by_id(auction_id)
    bids = list_bids_for_auction(auction_id)

    # Enrich latest bid with bidder_name (joined in list_bids_for_auction)
    bidder_name = None
    try:
        matched = next((b for b in bids if b.get("id") == bid.get("id")), None)
        if matched:
            bidder_name = matched.get("bidder_name")
    except Exception:
        bidder_name = None
    if bidder_name is not None:
        bid["bidder_name"] = bidder_name
    full_update = {
        "type": "update",
        "auction": auction,
        "bids": bids,
        "latest_bid": bid,
    }
    new_bid_message = {
        "type": "new_bid",
        "auction_id": auction_id,
        "amount": bid["amount"],
        "quantity": bid.get("quantity"),
        "bidder_id": bid["bidder_id"],
        "bidder_name": bid.get("bidder_name"),
        "created_at": bid.get("created_at"),
        "current_price": bid["amount"],
        "status": "active",
    }

    connections = list(active_auction_connections.get(auction_id, []))
    for ws in connections:
        if ws.client_state != WebSocketState.CONNECTED:
            continue
        try:
            await ws.send_json(jsonable_encoder(full_update))
            # Keep backward compatibility for clients listening only to "new_bid".
            await ws.send_json(jsonable_encoder(new_bid_message))
        except Exception as e:
            print(f"Error broadcasting bid to websocket client: {e}")
            current_connections = active_auction_connections.get(auction_id, [])
            if ws in current_connections:
                current_connections.remove(ws)
            if not current_connections:
                active_auction_connections.pop(auction_id, None)
