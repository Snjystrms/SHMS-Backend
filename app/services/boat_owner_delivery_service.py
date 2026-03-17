"""Boat owner delivery service: scan QR and record delivery for auctions sold by boat owner."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.db.session import get_db_connection
from app.services import user_service
from app.services.buyer_dashboard_service import (
    _auction_identifier,
    _auction_type_display,
    _format_start_time,
)

_IST = timezone(timedelta(hours=5, minutes=30))


def _normalize_uuid(value: str) -> str:
    """Normalize to standard UUID string for consistent DB comparison."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return str(value)


def get_delivery_by_qr(
    auction_id: str, buyer_id: str, boat_owner_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Fetch delivery detail for an auction by QR payload (auction_id, buyer_id).
    Only the boat owner (seller) can access this.
    Returns (detail_dict, None) on success, or (None, error_message) on failure.
    """
    aid = _normalize_uuid(auction_id)
    bid = _normalize_uuid(buyer_id)
    owner_id = _normalize_uuid(boat_owner_id)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.seller_id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                b.boat_number
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE a.id = %s AND a.winner_id = %s AND a.status = 'completed'
            """,
            (aid, bid),
        )
        r = cur.fetchone()
        if not r:
            return None, "Auction not found or buyer did not win"

        seller_id = str(r[1]) if r[1] else None
        if seller_id != owner_id:
            return None, "Auction does not belong to you"

        auction_id_str = str(r[0])
        fish_name = r[2] or ""
        auction_type = r[3] or "open_box"
        start_time = r[4]
        delivered_quantity = float(r[5] or 0)
        boat_number = r[6]

        cur.execute(
            """
            SELECT amount, quantity FROM bids
            WHERE auction_id = %s AND bidder_id = %s
            ORDER BY amount DESC LIMIT 1
            """,
            (auction_id_str, bid),
        )
        bid_row = cur.fetchone()
        my_bid = float(bid_row[0]) if bid_row else 0.0
        required_quantity = float(bid_row[1]) if bid_row and bid_row[1] is not None else 0.0

        user = user_service.get_user_by_id(bid)
        buyer_name = user.get("name", "") if user else ""

        return {
            "auction_id": auction_id_str,
            "buyer_name": buyer_name,
            "bid_price": my_bid,
            "auction_type": _auction_type_display(auction_type),
            "requested_quantity": required_quantity,
            "delivered_quantity": delivered_quantity,
            "fish_type": fish_name,
            "start_time": _format_start_time(start_time),
            "auction_identifier": _auction_identifier(auction_id_str, boat_number),
            "is_already_delivered": delivered_quantity > 0,
        }, None
    except Exception as e:
        print(f"Error fetching delivery by QR: {e}")
        return None, "Failed to fetch delivery details"
    finally:
        cur.close()
        conn.close()


def get_initiate_delivery_for_auction(
    auction_id: str, boat_owner_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Fetch delivery detail for a completed auction using its winner_id (no QR required).
    Only the boat owner (seller) can access this.
    Returns (detail_dict, None) on success, or (None, error_message) on failure.
    """
    aid = _normalize_uuid(auction_id)
    owner_id = _normalize_uuid(boat_owner_id)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.seller_id,
                a.winner_id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                b.boat_number
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE a.id = %s AND a.status = 'completed'
            """,
            (aid,),
        )
        r = cur.fetchone()
        if not r:
            return None, "Auction not found or not completed"

        seller_id = str(r[1]) if r[1] else None
        if seller_id != owner_id:
            return None, "Auction does not belong to you"

        winner_id = str(r[2]) if r[2] else None
        if not winner_id:
            return None, "Auction has no winner"

        auction_id_str = str(r[0])
        fish_name = r[3] or ""
        auction_type = r[4] or "open_box"
        start_time = r[5]
        delivered_quantity = float(r[6] or 0)
        boat_number = r[7]

        cur.execute(
            """
            SELECT amount, quantity FROM bids
            WHERE auction_id = %s AND bidder_id = %s
            ORDER BY amount DESC LIMIT 1
            """,
            (auction_id_str, winner_id),
        )
        bid_row = cur.fetchone()
        win_bid = float(bid_row[0]) if bid_row else 0.0
        requested_quantity = float(bid_row[1]) if bid_row and bid_row[1] is not None else 0.0

        user = user_service.get_user_by_id(winner_id)
        buyer_name = user.get("name", "") if user else ""

        return {
            "auction_id": auction_id_str,
            "buyer_name": buyer_name,
            "bid_price": win_bid,
            "auction_type": _auction_type_display(auction_type),
            "requested_quantity": requested_quantity,
            "delivered_quantity": delivered_quantity,
            "fish_type": fish_name,
            "start_time": _format_start_time(start_time),
            "auction_identifier": _auction_identifier(auction_id_str, boat_number),
            "is_already_delivered": delivered_quantity > 0,
        }, None
    except Exception as e:
        print(f"Error fetching initiate delivery details: {e}")
        return None, "Failed to fetch delivery details"
    finally:
        cur.close()
        conn.close()


def get_initiate_delivery_for_auction_by_agent(
    auction_id: str, agent_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Fetch delivery detail for a completed auction using its winner_id (no QR required).
    Agent can access only auctions that were created via the agent's approved bidding request.
    Returns (detail_dict, None) on success, or (None, error_message) on failure.
    """
    aid = _normalize_uuid(auction_id)
    agid = _normalize_uuid(agent_id)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.winner_id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                b.boat_number
            FROM auctions a
            JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = br.boat_id AND b.deleted_at IS NULL
            WHERE a.id = %s
              AND a.status = 'completed'
              AND br.agent_id = %s
            """,
            (aid, agid),
        )
        r = cur.fetchone()
        if not r:
            return None, "Auction not found or not completed"

        winner_id = str(r[1]) if r[1] else None
        if not winner_id:
            return None, "Auction has no winner"

        auction_id_str = str(r[0])
        fish_name = r[2] or ""
        auction_type = r[3] or "open_box"
        start_time = r[4]
        delivered_quantity = float(r[5] or 0)
        boat_number = r[6]

        cur.execute(
            """
            SELECT amount, quantity FROM bids
            WHERE auction_id = %s AND bidder_id = %s
            ORDER BY amount DESC LIMIT 1
            """,
            (auction_id_str, winner_id),
        )
        bid_row = cur.fetchone()
        win_bid = float(bid_row[0]) if bid_row else 0.0
        requested_quantity = float(bid_row[1]) if bid_row and bid_row[1] is not None else 0.0

        user = user_service.get_user_by_id(winner_id)
        buyer_name = user.get("name", "") if user else ""

        return {
            "auction_id": auction_id_str,
            "buyer_name": buyer_name,
            "bid_price": win_bid,
            "auction_type": _auction_type_display(auction_type),
            "requested_quantity": requested_quantity,
            "delivered_quantity": delivered_quantity,
            "fish_type": fish_name,
            "start_time": _format_start_time(start_time),
            "auction_identifier": _auction_identifier(auction_id_str, boat_number),
            "is_already_delivered": delivered_quantity > 0,
        }, None
    except Exception as e:
        print(f"Error fetching initiate delivery details (agent): {e}")
        return None, "Failed to fetch delivery details"
    finally:
        cur.close()
        conn.close()


def record_delivery(
    auction_id: str, boat_owner_id: str, delivered_quantity: float
) -> Tuple[bool, Optional[str]]:
    """
    Record delivered quantity for an auction. Only the boat owner (seller) can record.
    Returns (True, None) on success, or (False, error_message) on failure.
    """
    aid = _normalize_uuid(auction_id)
    owner_id = _normalize_uuid(boat_owner_id)

    if delivered_quantity <= 0:
        return False, "Delivered quantity must be greater than 0"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT a.id, a.seller_id, a.winner_id, a.delivered_quantity
            FROM auctions a
            WHERE a.id = %s AND a.status = 'completed'
            """,
            (aid,),
        )
        r = cur.fetchone()
        if not r:
            return False, "Auction not found or not completed"

        seller_id = str(r[1]) if r[1] else None
        winner_id = str(r[2]) if r[2] else None
        existing_delivered = float(r[3] or 0)

        if seller_id != owner_id:
            return False, "Auction does not belong to you"

        if existing_delivered > 0:
            return False, "Delivery already recorded"

        if not winner_id:
            return False, "Auction has no winner"

        cur.execute(
            """
            SELECT quantity FROM bids
            WHERE auction_id = %s AND bidder_id = %s
            ORDER BY amount DESC LIMIT 1
            """,
            (aid, winner_id),
        )
        bid_row = cur.fetchone()
        required_quantity = float(bid_row[0]) if bid_row and bid_row[0] is not None else 0.0

        if required_quantity > 0 and delivered_quantity > required_quantity:
            return False, f"Delivered quantity cannot exceed requested quantity ({required_quantity} KG)"

        cur.execute(
            """
            UPDATE auctions
            SET delivered_quantity = %s, updated_at = NOW()
            WHERE id = %s AND seller_id = %s
            """,
            (delivered_quantity, aid, owner_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return False, "Failed to update delivery"

        return True, None
    except Exception as e:
        conn.rollback()
        print(f"Error recording delivery: {e}")
        return False, "Failed to record delivery"
    finally:
        cur.close()
        conn.close()


def get_pending_deliveries_for_boat_owner(
    boat_owner_id: str,
) -> List[Dict[str, Any]]:
    """
    List completed auctions for this boat owner that are not fully delivered yet.
    Includes both not-started and in-progress (partial) deliveries.
    """
    owner_id = _normalize_uuid(boat_owner_id)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.seller_id,
                a.winner_id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                b.boat_number
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE a.seller_id = %s
              AND a.status = 'completed'
            ORDER BY a.start_time DESC
            """,
            (owner_id,),
        )
        rows = cur.fetchall() or []

        pending: List[Dict[str, Any]] = []

        for r in rows:
            auction_id = str(r[0])
            seller_id = str(r[1]) if r[1] else None
            winner_id = str(r[2]) if r[2] else None
            fish_name = r[3] or ""
            auction_type = r[4] or "open_box"
            start_time = r[5]
            delivered_quantity = float(r[6] or 0)
            boat_number = r[7]

            if seller_id != owner_id:
                continue
            if not winner_id:
                continue

            cur.execute(
                """
                SELECT amount, quantity
                FROM bids
                WHERE auction_id = %s AND bidder_id = %s
                ORDER BY amount DESC
                LIMIT 1
                """,
                (auction_id, winner_id),
            )
            bid_row = cur.fetchone()
            if not bid_row:
                continue

            bid_price = float(bid_row[0]) if bid_row[0] is not None else 0.0
            requested_quantity = (
                float(bid_row[1]) if bid_row[1] is not None else 0.0
            )

            if requested_quantity <= 0:
                continue
            if delivered_quantity >= requested_quantity:
                continue

            pending.append(
                {
                    "auction_id": auction_id,
                    "auction_identifier": _auction_identifier(auction_id, boat_number),
                    "fish_type": fish_name,
                    "auction_type": _auction_type_display(auction_type),
                    "bid_price": bid_price,
                    "requested_quantity": requested_quantity,
                    "delivered_quantity": delivered_quantity,
                    "start_time": _format_start_time(start_time),
                    "status": "Pending Delivery",
                }
            )

        return pending
    except Exception as e:
        print(f"Error fetching pending deliveries for boat owner: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_deliveries_for_boat_owner(
    boat_owner_id: str,
    status_filter: str = "pending",
) -> List[Dict[str, Any]]:
    """
    List deliveries for this boat owner filtered by status.

    status_filter:
    - "pending": completed auctions where delivered_quantity < requested_quantity
    - "completed": completed auctions where delivered_quantity >= requested_quantity
    """
    status_filter = (status_filter or "pending").strip().lower()
    if status_filter not in {"pending", "completed"}:
        return []

    owner_id = _normalize_uuid(boat_owner_id)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.seller_id,
                a.winner_id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                b.boat_number
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE a.seller_id = %s
              AND a.status = 'completed'
            ORDER BY a.start_time DESC
            """,
            (owner_id,),
        )
        rows = cur.fetchall() or []

        items: List[Dict[str, Any]] = []

        for r in rows:
            auction_id = str(r[0])
            seller_id = str(r[1]) if r[1] else None
            winner_id = str(r[2]) if r[2] else None
            fish_name = r[3] or ""
            auction_type = r[4] or "open_box"
            start_time = r[5]
            delivered_quantity = float(r[6] or 0)
            boat_number = r[7]

            if seller_id != owner_id:
                continue
            if not winner_id:
                continue

            cur.execute(
                """
                SELECT amount, quantity
                FROM bids
                WHERE auction_id = %s AND bidder_id = %s
                ORDER BY amount DESC
                LIMIT 1
                """,
                (auction_id, winner_id),
            )
            bid_row = cur.fetchone()
            if not bid_row:
                continue

            bid_price = float(bid_row[0]) if bid_row[0] is not None else 0.0
            requested_quantity = float(bid_row[1]) if bid_row[1] is not None else 0.0

            if requested_quantity <= 0:
                continue

            is_completed_delivery = delivered_quantity >= requested_quantity
            if status_filter == "pending" and is_completed_delivery:
                continue
            if status_filter == "completed" and not is_completed_delivery:
                continue

            items.append(
                {
                    "auction_id": auction_id,
                    "auction_identifier": _auction_identifier(auction_id, boat_number),
                    "fish_type": fish_name,
                    "auction_type": _auction_type_display(auction_type),
                    "bid_price": bid_price,
                    "requested_quantity": requested_quantity,
                    "delivered_quantity": delivered_quantity,
                    "start_time": _format_start_time(start_time),
                    "status": "Completed Delivery" if is_completed_delivery else "Pending Delivery",
                }
            )

        return items
    except Exception as e:
        print(f"Error fetching deliveries for boat owner: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_deliveries_for_agent(
    agent_id: str,
    status_filter: str = "pending",
) -> List[Dict[str, Any]]:
    """
    List deliveries for an agent filtered by status.
    Includes only auctions created via the agent's bidding requests.

    status_filter:
    - "pending": completed auctions where delivered_quantity < requested_quantity
    - "completed": completed auctions where delivered_quantity >= requested_quantity
    """
    status_filter = (status_filter or "pending").strip().lower()
    if status_filter not in {"pending", "completed"}:
        return []

    agid = _normalize_uuid(agent_id)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.winner_id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                b.boat_number
            FROM auctions a
            JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = br.boat_id AND b.deleted_at IS NULL
            WHERE a.status = 'completed'
              AND br.agent_id = %s
            ORDER BY a.start_time DESC
            """,
            (agid,),
        )
        rows = cur.fetchall() or []

        items: List[Dict[str, Any]] = []

        for r in rows:
            auction_id = str(r[0])
            winner_id = str(r[1]) if r[1] else None
            fish_name = r[2] or ""
            auction_type = r[3] or "open_box"
            start_time = r[4]
            delivered_quantity = float(r[5] or 0)
            boat_number = r[6]

            if not winner_id:
                continue

            cur.execute(
                """
                SELECT amount, quantity
                FROM bids
                WHERE auction_id = %s AND bidder_id = %s
                ORDER BY amount DESC
                LIMIT 1
                """,
                (auction_id, winner_id),
            )
            bid_row = cur.fetchone()
            if not bid_row:
                continue

            bid_price = float(bid_row[0]) if bid_row[0] is not None else 0.0
            requested_quantity = float(bid_row[1]) if bid_row[1] is not None else 0.0

            if requested_quantity <= 0:
                continue

            is_completed_delivery = delivered_quantity >= requested_quantity
            if status_filter == "pending" and is_completed_delivery:
                continue
            if status_filter == "completed" and not is_completed_delivery:
                continue

            items.append(
                {
                    "auction_id": auction_id,
                    "auction_identifier": _auction_identifier(auction_id, boat_number),
                    "fish_type": fish_name,
                    "auction_type": _auction_type_display(auction_type),
                    "bid_price": bid_price,
                    "requested_quantity": requested_quantity,
                    "delivered_quantity": delivered_quantity,
                    "start_time": _format_start_time(start_time),
                    "status": "Completed Delivery" if is_completed_delivery else "Pending Delivery",
                }
            )

        return items
    except Exception as e:
        print(f"Error fetching deliveries for agent: {e}")
        return []
    finally:
        cur.close()
        conn.close()
