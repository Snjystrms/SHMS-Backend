"""Buyer history service: auction history and delivery history for won auctions."""

import uuid
from typing import Any, Dict, List

from app.db.session import get_db_connection
from app.services.buyer_dashboard_service import (
    _auction_identifier,
    _auction_type_display,
    _format_start_time,
)


def _normalize_uuid(value: str) -> str:
    """Normalize to standard UUID string for consistent DB comparison."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return str(value)


def list_auction_history(buyer_id: str) -> List[Dict[str, Any]]:
    """
    Return auction history: completed auctions where the buyer won.
    Status "Bid Won", includes fish_type, bid_price (winning), auction_type, start_time, my_bid, required_quantity.
    """
    user_id = _normalize_uuid(buyer_id)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.fish_name,
                a.current_price,
                a.auction_type,
                a.start_time,
                b.boat_number,
                b.boat_name
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE a.winner_id = %s AND a.status = 'completed'
            ORDER BY a.start_time DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()

        auctions: List[Dict[str, Any]] = []
        for r in rows:
            auction_id = str(r[0])
            fish_name = r[1] or ""
            current_price = float(r[2] or 0)
            auction_type = r[3] or "open_box"
            start_time = r[4]
            boat_number = r[5]
            boat_name = r[6] or ""

            cur.execute(
                """
                SELECT amount, quantity FROM bids
                WHERE auction_id = %s AND bidder_id = %s
                ORDER BY amount DESC LIMIT 1
                """,
                (auction_id, user_id),
            )
            bid_row = cur.fetchone()
            my_bid = float(bid_row[0]) if bid_row else 0.0
            required_quantity = float(bid_row[1]) if bid_row and bid_row[1] is not None else 0.0

            auctions.append({
                "auction_id": auction_id,
                "auction_identifier": _auction_identifier(auction_id, boat_number),
                "description": boat_name or fish_name or "Auction",
                "status": "Bid Won",
                "fish_type": fish_name,
                "bid_price": current_price,
                "auction_type": _auction_type_display(auction_type),
                "start_time": _format_start_time(start_time),
                "my_bid": my_bid,
                "required_quantity": required_quantity,
            })

        return auctions
    except Exception as e:
        print(f"Error listing auction history: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def list_delivery_history(buyer_id: str) -> List[Dict[str, Any]]:
    """
    Return delivery history: completed auctions where the buyer won.
    Status "Delivery Completed", includes my_bid, required_quantity, delivered_quantity.
    """
    user_id = _normalize_uuid(buyer_id)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.fish_name,
                a.delivered_quantity,
                a.delivery_status,
                a.delivered_at,
                b.boat_number,
                b.boat_name
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE a.winner_id = %s
              AND a.status = 'completed'
              AND a.delivery_status = 'completed'
            ORDER BY a.start_time DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()

        deliveries: List[Dict[str, Any]] = []
        for r in rows:
            auction_id = str(r[0])
            fish_name = r[1] or ""
            delivered_quantity = float(r[2] or 0)
            delivery_status = (r[3] or "").strip().lower() or "completed"
            delivered_at = r[4]
            boat_number = r[5]
            boat_name = r[6] or ""

            cur.execute(
                """
                SELECT amount, quantity FROM bids
                WHERE auction_id = %s AND bidder_id = %s
                ORDER BY amount DESC LIMIT 1
                """,
                (auction_id, user_id),
            )
            bid_row = cur.fetchone()
            my_bid = float(bid_row[0]) if bid_row else 0.0
            required_quantity = float(bid_row[1]) if bid_row and bid_row[1] is not None else 0.0

            deliveries.append({
                "delivery_id": auction_id,
                "auction_identifier": _auction_identifier(auction_id, boat_number),
                "description": boat_name or fish_name or "Delivery",
                "status": "Delivery Completed",
                "my_bid": my_bid,
                "required_quantity": required_quantity,
                "delivered_quantity": delivered_quantity,
                "delivery_status": delivery_status,
                "delivered_at": delivered_at,
            })

        return deliveries
    except Exception as e:
        print(f"Error listing delivery history: {e}")
        return []
    finally:
        cur.close()
        conn.close()
