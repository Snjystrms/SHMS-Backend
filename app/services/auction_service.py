import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi.encoders import jsonable_encoder
from fastapi.websockets import WebSocketState

from app.db.session import get_db_connection
from app.schemas.auction import AuctionStatus
from app.api.v1.endpoints.auction_ws import active_auction_connections
from app.services import user_service
from app.services.buyer_dashboard_service import (
    _auction_identifier,
    _auction_type_display,
    _format_start_time,
)

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
    sale = row[5]
    start = row[6]
    end = row[7]
    return {
        "id": str(row[0]),
        "seller_id": str(row[1]),
        "fish_name": row[2],
        "initial_price": float(row[3]),
        "current_price": float(row[4]),
        "sale": (float(sale) if sale is not None else None),
        "start_time": _normalize_to_ist(start) if start else None,
        "end_time": _normalize_to_ist(end) if end else None,
        "status": row[8],
        "winner_id": str(row[9]) if row[9] else None,
        "bidding_request_id": str(row[10]) if len(row) > 10 and row[10] else None,
        "auction_type": row[11] if len(row) > 11 else "open_box",
        "movement_id": str(row[12]) if len(row) > 12 and row[12] else None,
    }


def get_last_auctions_for_boat(boat_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Return last N auctions related to a boat (via movement.boat_id or bidding_request.boat_id),
    ordered by start_time / created_at descending, including winner and delivery summary.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.status,
                a.winner_id,
                a.delivered_quantity,
                b.boat_number
            FROM auctions a
            LEFT JOIN boat_movements m
              ON m.id = a.movement_id
            LEFT JOIN bidding_requests br
              ON br.id = a.bidding_request_id
            LEFT JOIN boats b
              ON b.id = COALESCE(m.boat_id, br.boat_id)
             AND b.deleted_at IS NULL
            WHERE COALESCE(m.boat_id, br.boat_id) = %s
            ORDER BY a.start_time DESC NULLS LAST, a.created_at DESC
            LIMIT %s
            """,
            (boat_id, limit),
        )
        rows = cur.fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            auction_id = str(r[0])
            fish_name = r[1] or ""
            auction_type = r[2] or "open_box"
            start_time = r[3]
            status = r[4]
            winner_id = str(r[5]) if r[5] else None
            delivered_quantity = float(r[6] or 0.0)
            boat_number = r[7]

            winner_name: Optional[str] = None
            bid_price: Optional[float] = None
            requested_quantity: Optional[float] = None

            if winner_id:
                cur.execute(
                    """
                    SELECT amount, quantity
                    FROM bids
                    WHERE auction_id = %s AND bidder_id = %s
                    ORDER BY amount DESC, created_at ASC
                    LIMIT 1
                    """,
                    (auction_id, winner_id),
                )
                bid_row = cur.fetchone()
                if bid_row:
                    bid_price = float(bid_row[0])
                    requested_quantity = (
                        float(bid_row[1]) if bid_row[1] is not None else None
                    )
                user = user_service.get_user_by_id(winner_id)
                if user:
                    winner_name = user.get("name") or None

            results.append(
                {
                    "auction_id": auction_id,
                    "fish_type": fish_name,
                    "auction_type": _auction_type_display(auction_type),
                    "start_time": _format_start_time(start_time) if start_time else None,
                    "status": status,
                    "winner_name": winner_name,
                    "bid_price": bid_price,
                    "requested_quantity": requested_quantity,
                    "delivered_quantity": delivered_quantity,
                    "auction_identifier": _auction_identifier(auction_id, boat_number),
                }
            )
        return results
    finally:
        cur.close()
        conn.close()


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
            "sale": None,
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
              AND status IN ('scheduled', 'active')
            """,
            (auction_id,),
        )
        conn.commit()

        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price, sale,
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
            SELECT id, seller_id, fish_name, initial_price, current_price, sale,
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


def list_auctions_for_seller(seller_id: str) -> List[Dict[str, Any]]:
    """
    Return auctions for a specific seller (boat owner), including:
    - Self-created auctions (movement_id-based).
    - Auctions created by an agent from an approved bidding request where this
      boat owner is the seller (seller_id stored as boat_owner_id).
    Status is lazily updated using the same IST-based logic as list_auctions().
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Lazily update status for this seller's scheduled/active auctions.
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
              AND seller_id = %s
            """,
            (seller_id,),
        )
        conn.commit()

        cur.execute(
            """
            SELECT id, seller_id, fish_name, initial_price, current_price, sale,
                   start_time, end_time, status, winner_id, bidding_request_id, auction_type, movement_id
            FROM auctions
            WHERE seller_id = %s
            ORDER BY created_at DESC
            """,
            (seller_id,),
        )
        rows = cur.fetchall()
        return [_auction_from_row(r) for r in rows]
    except Exception as e:
        conn.rollback()
        print(f"Error listing auctions for seller {seller_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def list_auctions_for_agent(agent_id: str) -> List[Dict[str, Any]]:
    """
    Return auctions created by the given agent (via approved bidding requests).

    Note: movement_id-based (boat owner self) auctions are not included because they
    don't have a bidding_request_id to link back to an agent.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Lazily update status only for this agent's scheduled/active auctions.
        cur.execute(
            f"""
            UPDATE auctions
            SET status = CASE
                    WHEN {_NOW_IST_SQL} >= end_time THEN 'completed'
                    WHEN {_NOW_IST_SQL} >= start_time THEN 'active'
                    ELSE auctions.status
                END,
                updated_at = NOW()
            FROM bidding_requests br
            WHERE auctions.bidding_request_id = br.id
              AND br.agent_id = %s
              AND auctions.status IN ('scheduled', 'active')
            """,
            (agent_id,),
        )
        conn.commit()

        cur.execute(
            """
            SELECT
                a.id, a.seller_id, a.fish_name, a.initial_price, a.current_price, a.sale,
                a.start_time, a.end_time, a.status, a.winner_id, a.bidding_request_id, a.auction_type, a.movement_id
            FROM auctions a
            JOIN bidding_requests br ON br.id = a.bidding_request_id
            WHERE br.agent_id = %s
            ORDER BY a.created_at DESC
            """,
            (agent_id,),
        )
        rows = cur.fetchall()
        return [_auction_from_row(r) for r in rows]
    except Exception as e:
        conn.rollback()
        print(f"Error listing auctions for agent {agent_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def list_agent_auction_cards(agent_id: str, status: str) -> List[Dict[str, Any]]:
    """
    UI-ready auctions list for Agent app.

    Filters by status in {"active", "completed"} and returns card fields:
    - Ongoing: auction_identifier, boat_name, fish_type, bid_price, auction_type, start_time, status=Live
    - Completed: auction_identifier, boat_name, winner_name, bid_price, auction_type, delivered_quantity, status=Completed
    """
    status_value = (status or "active").strip().lower()
    if status_value not in {"active", "completed"}:
        return []

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Lazily update status only for this agent's scheduled/active auctions.
        cur.execute(
            f"""
            UPDATE auctions
            SET status = CASE
                    WHEN {_NOW_IST_SQL} >= end_time THEN 'completed'
                    WHEN {_NOW_IST_SQL} >= start_time THEN 'active'
                    ELSE auctions.status
                END,
                updated_at = NOW()
            FROM bidding_requests br
            WHERE auctions.bidding_request_id = br.id
              AND br.agent_id = %s
              AND auctions.status IN ('scheduled', 'active')
            """,
            (agent_id,),
        )
        conn.commit()

        cur.execute(
            """
            SELECT
                a.id,
                a.fish_name,
                a.current_price,
                a.auction_type,
                a.start_time,
                a.status,
                a.delivered_quantity,
                b.boat_number,
                b.boat_name,
                u.name AS winner_name
            FROM auctions a
            JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN boats b
              ON b.id = COALESCE(m.boat_id, br.boat_id)
             AND b.deleted_at IS NULL
            LEFT JOIN users u ON u.id = a.winner_id
            WHERE br.agent_id = %s
              AND a.status = %s
            ORDER BY a.start_time DESC NULLS LAST, a.created_at DESC
            """,
            (agent_id, status_value),
        )
        rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            auction_id = str(r[0])
            fish_name = r[1] or ""
            current_price = float(r[2] or 0.0)
            auction_type = r[3] or "open_box"
            start_time = r[4]
            row_status = (r[5] or "").strip().lower()
            delivered_quantity = float(r[6] or 0.0)
            boat_number = r[7]
            boat_name = (r[8] or "").strip()
            winner_name = r[9]

            is_completed = row_status == "completed"
            start_time_display: Optional[str] = None
            if not is_completed and start_time:
                start_time_display = _format_start_time(start_time)
            results.append(
                {
                    "auction_id": auction_id,
                    "auction_identifier": _auction_identifier(auction_id, boat_number),
                    "boat_name": boat_name or fish_name or "Auction",
                    "status": "Completed" if is_completed else "Live",
                    "fish_type": (None if is_completed else fish_name),
                    "bid_price": current_price,
                    "auction_type": _auction_type_display(auction_type),
                    "start_time": start_time_display,
                    "winner_name": (winner_name if is_completed else None),
                    "delivered_quantity": (delivered_quantity if is_completed else None),
                }
            )

        return results
    except Exception as e:
        conn.rollback()
        print(f"Error listing agent auction cards for agent {agent_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def list_active_auctions() -> List[Dict[str, Any]]:
    """Return only currently active auctions (status='active')."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Lazily update status for scheduled/active auctions across all sellers.
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
            SELECT id, seller_id, fish_name, initial_price, current_price, sale,
                   start_time, end_time, status, winner_id, bidding_request_id, auction_type, movement_id
            FROM auctions
            WHERE status = 'active'
            ORDER BY created_at DESC
            """,
        )
        rows = cur.fetchall()
        return [_auction_from_row(r) for r in rows]
    except Exception as e:
        conn.rollback()
        print(f"Error listing active auctions: {e}")
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
            SELECT id, seller_id, fish_name, initial_price, current_price, sale,
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
            SELECT id, seller_id, fish_name, initial_price, current_price, sale,
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
            auction["_ended_now"] = False
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
        auction["_ended_now"] = True
        return auction
    except Exception as e:
        conn.rollback()
        print(f"Error ending auction: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def end_auction_by_agent(auction_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
    """
    Manually end an auction (agent-created auctions only):
    - Only the agent who created the auction (via bidding_request) can end it.
    - Sets status to 'completed'.
    - Sets winner_id to highest bidder (if any).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id, a.seller_id, a.fish_name, a.initial_price, a.current_price, a.sale,
                a.start_time, a.end_time, a.status, a.winner_id, a.bidding_request_id, a.auction_type, a.movement_id
            FROM auctions a
            JOIN bidding_requests br ON br.id = a.bidding_request_id
            WHERE a.id = %s AND br.agent_id = %s
            """,
            (auction_id, agent_id),
        )
        row = cur.fetchone()
        if not row:
            return None

        auction = _auction_from_row(row)
        if auction["status"] == "completed":
            auction["_ended_now"] = False
            return auction

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
        auction["_ended_now"] = True
        return auction
    except Exception as e:
        conn.rollback()
        print(f"Error ending auction by agent: {e}")
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
            SELECT id, seller_id, fish_name, initial_price, current_price, sale,
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
    # Enrich latest bid with bidder_name (joined in list_bids_for_auction)
    bidder_name = None
    try:
        bids = list_bids_for_auction(auction_id)
        matched = next((b for b in bids if b.get("id") == bid.get("id")), None)
        if matched:
            bidder_name = matched.get("bidder_name")
    except Exception:
        bidder_name = None
    if bidder_name is not None:
        bid["bidder_name"] = bidder_name
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
            # Send a single message per bid to avoid duplicate UI updates.
            await ws.send_json(jsonable_encoder(new_bid_message))
        except Exception as e:
            print(f"Error broadcasting bid to websocket client: {e}")
            current_connections = active_auction_connections.get(auction_id, [])
            if ws in current_connections:
                current_connections.remove(ws)
            if not current_connections:
                active_auction_connections.pop(auction_id, None)


async def broadcast_auction_ended(auction: Dict[str, Any]) -> None:
    """
    Notify all clients connected to this auction's WebSocket that it ended.

    Message format (JSON):
    {
        "type": "auction_ended",
        "auction_id": "<auction UUID>",
        "winner_id": "<user UUID>|null",
        "current_price": <float>,
        "auction": { ...full auction payload... }
    }
    """
    auction_id = str(auction.get("id") or "")
    if not auction_id:
        return

    message = {
        "type": "auction_ended",
        "auction_id": auction_id,
        "winner_id": auction.get("winner_id"),
        "current_price": auction.get("current_price"),
        "auction": auction,
    }

    connections = list(active_auction_connections.get(auction_id, []))
    for ws in connections:
        if ws.client_state != WebSocketState.CONNECTED:
            continue
        try:
            await ws.send_json(jsonable_encoder(message))
        except Exception as e:
            print(f"Error broadcasting auction end to websocket client: {e}")
            current_connections = active_auction_connections.get(auction_id, [])
            if ws in current_connections:
                current_connections.remove(ws)
            if not current_connections:
                active_auction_connections.pop(auction_id, None)
