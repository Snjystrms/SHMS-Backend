"""Admin delivery service: list deliveries by buyer id."""

import uuid
from typing import Any, Dict, List, Optional

from app.db.session import get_db_connection
from app.services.buyer_dashboard_service import (
    _auction_identifier,
    _auction_type_display,
    _format_start_time,
)


def _get_location(port_name: Optional[str], harbor_name: Optional[str]) -> str:
    if port_name and str(port_name).strip():
        return str(port_name).strip()
    if harbor_name and str(harbor_name).strip():
        return str(harbor_name).strip()
    return "Unknown"


def _normalize_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return str(value)


def _get_bid_info(cur, auction_id: str, bidder_id: str) -> tuple[float, float]:
    cur.execute(
        """
        SELECT amount, quantity FROM bids
        WHERE auction_id = %s AND bidder_id = %s
        ORDER BY amount DESC LIMIT 1
        """,
        (auction_id, bidder_id),
    )
    bid_row = cur.fetchone()
    my_bid = float(bid_row[0]) if bid_row else 0.0
    required_quantity = (
        float(bid_row[1]) if bid_row and bid_row[1] is not None else 0.0
    )
    return my_bid, required_quantity


def _delivery_list_item_from_row(row, buyer_id: str) -> Dict[str, Any]:
    auction_id = str(row[0])
    fish_name = row[1] or ""
    initial_price = float(row[2] or 0)
    sale = float(row[3]) if row[3] is not None else None
    auction_type = row[4] or "open_box"
    start_time = row[5]
    delivered_quantity = float(row[6] or 0.0)
    delivery_status = (row[7] or "pending").strip().lower()
    delivered_at = row[8]
    boat_number = row[9]
    harbor_name = row[10]
    port_name = row[11]

    return {
        "delivery_id": auction_id,
        "auction_identifier": _auction_identifier(auction_id, boat_number),
        "location": _get_location(port_name, harbor_name),
        "status": "Completed Delivery" if delivery_status == "completed" else "Pending Delivery",
        "fish_type": fish_name,
        "bid_price": initial_price,
        "auction_type": _auction_type_display(auction_type),
        "start_time": _format_start_time(start_time),
        "my_bid": 0.0,
        "required_quantity": 0.0,
        "delivered_quantity": delivered_quantity,
        "sale": sale,
        "delivery_status": "completed" if delivery_status == "completed" else "pending",
        "delivered_at": delivered_at,
        "_buyer_id": buyer_id,
    }


def list_buyer_deliveries_for_admin(
    buyer_id: str,
    status_filter: str,
) -> List[Dict[str, Any]]:
    """
    Return list of deliveries for a buyer filtered by delivery_status (pending/completed).
    """
    user_id = _normalize_uuid(buyer_id)
    status_value = (status_filter or "pending").strip().lower()
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
            WHERE a.winner_id = %s
              AND a.status = 'completed'
              AND a.delivery_status = %s
            ORDER BY a.start_time DESC
            """,
            (user_id, status_value),
        )
        rows = cur.fetchall()

        deliveries: List[Dict[str, Any]] = []
        for r in rows:
            base = _delivery_list_item_from_row(r, buyer_id=user_id)
            my_bid, required_quantity = _get_bid_info(cur, base["delivery_id"], user_id)
            base["my_bid"] = my_bid
            base["required_quantity"] = required_quantity
            base.pop("_buyer_id", None)
            deliveries.append(base)

        return deliveries
    except Exception as e:
        print(f"Error listing admin buyer deliveries: {e}")
        return []
    finally:
        cur.close()
        conn.close()
