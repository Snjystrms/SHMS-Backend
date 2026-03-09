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


def _auction_from_row(row) -> Dict[str, Any]:
    """Map auctions table row to dict."""
    return {
        "id": str(row[0]),
        "seller_id": str(row[1]),
        "fish_name": row[2],
        "initial_price": float(row[3]),
        "current_price": float(row[4]),
        "start_time": row[5],
        "end_time": row[6],
        "status": row[7],
        "winner_id": str(row[8]) if row[8] else None,
    }


def create_auction(
    seller_id: str,
    fish_name: str,
    initial_price: float,
    start_time: datetime,
    end_time: datetime,
) -> Optional[Dict[str, Any]]:
    """Insert new auction into DB."""
    if end_time <= start_time:
        return None

    auction_id = str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO auctions (
                id, seller_id, fish_name, initial_price, current_price,
                start_time, end_time, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'scheduled')
            """,
            (
                auction_id,
                seller_id,
                fish_name.strip(),
                initial_price,
                initial_price,
                start_time,
                end_time,
            ),
        )
        conn.commit()
        return {
            "id": auction_id,
            "seller_id": seller_id,
            "fish_name": fish_name.strip(),
            "initial_price": initial_price,
            "current_price": initial_price,
            "start_time": start_time,
            "end_time": end_time,
            "status": "scheduled",
            "winner_id": None,
        }
    except Exception as e:
        conn.rollback()
        print(f"Error creating auction: {e}")
        return None
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
                   start_time, end_time, status, winner_id
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
                   start_time, end_time, status, winner_id
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
    end_time: Optional[datetime],
) -> Optional[Dict[str, Any]]:
    """Update editable fields of an auction owned by seller_id."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch existing auction to validate ownership and state
        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price,
                   start_time, end_time, status, winner_id
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
        new_start_time = start_time or auction["start_time"]
        new_end_time = end_time or auction["end_time"]

        if new_end_time <= new_start_time:
            return None

        cur.execute(
            """
            UPDATE auctions
            SET fish_name = %s,
                start_time = %s,
                end_time = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (new_fish_name, new_start_time, new_end_time, auction_id),
        )
        conn.commit()

        auction["fish_name"] = new_fish_name
        auction["start_time"] = new_start_time
        auction["end_time"] = new_end_time
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
                   start_time, end_time, status, winner_id
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
    """Return all bids for a specific auction, ordered by amount DESC then created_at ASC."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, auction_id, bidder_id, amount, created_at
            FROM bids
            WHERE auction_id = %s
            ORDER BY amount DESC, created_at ASC
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
                "created_at": r[4],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error listing bids for auction {auction_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def create_bid(auction_id: str, bidder_id: str, amount: float) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
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
                   start_time, end_time, status, winner_id
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
            INSERT INTO bids (id, auction_id, bidder_id, amount, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (bid_id, auction_id, bidder_id, amount, created_at),
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

        return {
            "id": bid_id,
            "auction_id": auction_id,
            "bidder_id": bidder_id,
            "amount": amount,
            "created_at": created_at,
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
        "bidder_id": bid["bidder_id"],
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
