"""Buyer dashboard service: summary stats and live auctions with buyer's bid."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.db.session import get_db_connection

_NOW_IST_SQL = "NOW() + INTERVAL '5 hours 30 minutes'"
_IST = timezone(timedelta(hours=5, minutes=30))


def _format_start_time(dt: datetime) -> str:
    """Format datetime as '01:30 PM' in IST."""
    if dt is None:
        return ""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=_IST)
    else:
        dt = dt.astimezone(_IST)
    return dt.strftime("%I:%M %p")


def _auction_type_display(auction_type: str) -> str:
    """Map auction_type to display string."""
    if auction_type == "dutch":
        return "Dutch"
    return "Open Box"


def _auction_identifier(auction_id: str, boat_number: Optional[str]) -> str:
    """Use boat_number when available, else shortened auction UUID."""
    if boat_number and str(boat_number).strip():
        return str(boat_number).strip()
    return str(auction_id)[:8].upper() if auction_id else ""


def get_buyer_dashboard(buyer_id: str) -> Dict[str, Any]:
    """
    Return buyer dashboard data: user summary, total_bids, pending_delivery,
    and live auctions with buyer's bid for each.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        now_ist = datetime.now(_IST)

        # 1 + 2. Total bids and pending delivery counts in one roundtrip.
        cur.execute(
            """
            SELECT
                COALESCE((SELECT COUNT(*) FROM bids WHERE bidder_id = %s), 0) AS total_bids,
                COALESCE((
                    SELECT COUNT(*)
                    FROM auctions
                    WHERE winner_id = %s
                      AND status = 'completed'
                ), 0) AS pending_delivery
            """,
            (buyer_id, buyer_id),
        )
        total_bids, pending_delivery = cur.fetchone() or (0, 0)
        total_bids = int(total_bids or 0)
        pending_delivery = int(pending_delivery or 0)

        # 3. Update only rows whose status should transition now.
        cur.execute(
            f"""
            UPDATE auctions
            SET status = CASE
                    WHEN {_NOW_IST_SQL} >= end_time THEN 'completed'
                    WHEN {_NOW_IST_SQL} >= start_time THEN 'active'
                    ELSE status
                END,
                updated_at = NOW()
            WHERE (status = 'scheduled' AND {_NOW_IST_SQL} >= start_time)
               OR (status = 'active' AND {_NOW_IST_SQL} >= end_time)
            """
        )
        conn.commit()

        # 4. Live auctions: active only, with boat info and buyer's highest bid.
        cur.execute(
            """
            SELECT
                a.id,
                a.fish_name,
                a.current_price,
                a.auction_type,
                a.start_time,
                b.boat_number,
                b.boat_name,
                mb.my_bid
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            LEFT JOIN (
                SELECT auction_id, MAX(amount) AS my_bid
                FROM bids
                WHERE bidder_id = %s
                GROUP BY auction_id
            ) mb ON mb.auction_id = a.id
            WHERE a.status = 'active'
            ORDER BY a.start_time ASC
            """,
            (buyer_id,),
        )
        auction_rows = cur.fetchall()

        live_auctions: List[Dict[str, Any]] = []
        for r in auction_rows:
            auction_id = str(r[0])
            fish_name = r[1] or ""
            current_price = float(r[2] or 0)
            auction_type = r[3] or "open_box"
            start_time = r[4]
            boat_number = r[5]
            boat_name = r[6] or ""
            my_bid = float(r[7]) if r[7] is not None else None

            live_auctions.append({
                "auction_id": auction_id,
                "auction_identifier": _auction_identifier(auction_id, boat_number),
                "item_title": boat_name or fish_name or "Auction",
                "status": "Live",
                "fish_type": fish_name,
                "current_bid_price": current_price,
                "auction_type": _auction_type_display(auction_type),
                "start_time": _format_start_time(start_time),
                "my_bid": my_bid,
                "required_quantity": None,
            })

        return {
            "total_bids": total_bids,
            "pending_delivery": pending_delivery,
            "live_auctions": live_auctions,
            "updated_at": now_ist,
        }
    except Exception as e:
        print(f"Error fetching buyer dashboard: {e}")
        return {
            "total_bids": 0,
            "pending_delivery": 0,
            "live_auctions": [],
            "updated_at": now_ist,
        }
    finally:
        cur.close()
        conn.close()
