"""Buyer delivery service: list and detail for auctions won by the buyer."""

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.db.session import get_db_connection
from app.services import user_service
from app.services.buyer_dashboard_service import (
    _auction_identifier,
    _auction_type_display,
    _format_start_time,
)

_IST = timezone(timedelta(hours=5, minutes=30))


def _get_location(port_name: Optional[str], harbor_name: Optional[str]) -> str:
    """Location = port_name when available, else harbor_name, else Unknown."""
    if port_name and str(port_name).strip():
        return str(port_name).strip()
    if harbor_name and str(harbor_name).strip():
        return str(harbor_name).strip()
    return "Unknown"


def _normalize_uuid(value: str) -> str:
    """Normalize to standard UUID string for consistent DB comparison."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return str(value)


def list_deliveries(buyer_id: str) -> List[Dict[str, Any]]:
    """
    Return list of deliveries (completed auctions) where the buyer won.
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
                a.initial_price,
                a.sale,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                a.delivery_status,
                a.delivered_at,
                b.boat_number,
                b.harbor_name,
                m.port_name
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

        deliveries: List[Dict[str, Any]] = []
        for r in rows:
            auction_id = str(r[0])
            fish_name = r[1] or ""
            initial_price = float(r[2] or 0)
            sale = float(r[3]) if r[3] is not None else None
            auction_type = r[4] or "open_box"
            start_time = r[5]
            delivered_quantity = float(r[6] or 0.0)
            delivery_status = (r[7] or "pending").strip().lower()
            delivered_at = r[8]
            boat_number = r[9]
            harbor_name = r[10]
            port_name = r[11]

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
                "location": _get_location(port_name, harbor_name),
                "status": "Completed Delivery" if delivery_status == "completed" else "Pending Delivery",
                "fish_type": fish_name,
                "bid_price": initial_price,
                "auction_type": _auction_type_display(auction_type),
                "start_time": _format_start_time(start_time),
                "my_bid": my_bid,
                "required_quantity": required_quantity,
                "delivered_quantity": delivered_quantity,
                "sale": sale,
                "delivery_status": "completed" if delivery_status == "completed" else "pending",
                "delivered_at": delivered_at,
            })

        return deliveries
    except Exception as e:
        print(f"Error listing buyer deliveries: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_delivery_detail(delivery_id: str, buyer_id: str) -> Optional[Dict[str, Any]]:
    """
    Return delivery detail for one auction. Returns None if not found or not owned by buyer.
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
                a.initial_price,
                a.sale,
                a.auction_type,
                a.start_time,
                a.delivered_quantity,
                a.delivery_status,
                a.delivered_at,
                b.boat_number,
                b.harbor_name,
                m.port_name
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE a.id = %s AND a.winner_id = %s AND a.status = 'completed'
            """,
            (delivery_id, user_id),
        )
        r = cur.fetchone()
        if not r:
            return None

        auction_id = str(r[0])
        fish_name = r[1] or ""
        initial_price = float(r[2] or 0)
        sale = float(r[3]) if r[3] is not None else None
        auction_type = r[4] or "open_box"
        start_time = r[5]
        delivered_quantity = float(r[6] or 0.0)
        delivery_status = (r[7] or "pending").strip().lower()
        delivered_at = r[8]
        boat_number = r[9]
        harbor_name = r[10]
        port_name = r[11]

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

        user = user_service.get_user_by_id(user_id)
        buyer_name = user.get("name", "") if user else ""

        qr_payload = json.dumps({
            "auction_id": auction_id,
            "buyer_id": user_id,
        })

        return {
            "delivery_id": auction_id,
            "auction_identifier": _auction_identifier(auction_id, boat_number),
            "location": _get_location(port_name, harbor_name),
            "status": "Completed Delivery" if delivery_status == "completed" else "Pending Delivery",
            "fish_type": fish_name,
            "bid_price": initial_price,
            "auction_type": _auction_type_display(auction_type),
            "start_time": _format_start_time(start_time),
            "my_bid": my_bid,
            "required_quantity": required_quantity,
            "delivered_quantity": delivered_quantity,
            "sale": sale,
            "delivery_status": "completed" if delivery_status == "completed" else "pending",
            "delivered_at": delivered_at,
            "buyer_name": buyer_name,
            "qr_payload": qr_payload,
        }
    except Exception as e:
        print(f"Error fetching delivery detail: {e}")
        return None
    finally:
        cur.close()
        conn.close()
