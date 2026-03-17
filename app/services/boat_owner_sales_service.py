"""Boat owner sales service: sales report (per-auction rows + totals)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db.session import get_db_connection
from app.services.buyer_dashboard_service import _auction_identifier, _auction_type_display

_IST = timezone(timedelta(hours=5, minutes=30))


@dataclass(frozen=True)
class _Range:
    from_ts: Optional[datetime]
    to_ts: Optional[datetime]


def _ist_now() -> datetime:
    return datetime.now(_IST)


def _date_to_ist_start(d: date) -> datetime:
    return datetime.combine(d, time.min).replace(tzinfo=_IST)


def _date_to_ist_end_exclusive(d: date) -> datetime:
    # Exclusive upper bound: start of next day (IST)
    return _date_to_ist_start(d) + timedelta(days=1)


def _compute_range(
    filter_name: str,
    from_date: Optional[date],
    to_date: Optional[date],
) -> _Range:
    f = (filter_name or "last_three_months").strip().lower()
    now = _ist_now()

    if f == "custom":
        if not from_date or not to_date:
            raise ValueError("from_date and to_date are required for custom filter")
        if to_date < from_date:
            raise ValueError("to_date must be on/after from_date")
        return _Range(
            from_ts=_date_to_ist_start(from_date),
            to_ts=_date_to_ist_end_exclusive(to_date),
        )

    if f == "last_week":
        return _Range(from_ts=now - timedelta(days=7), to_ts=None)
    if f == "last_month":
        return _Range(from_ts=now - timedelta(days=30), to_ts=None)
    if f == "last_three_months":
        return _Range(from_ts=now - timedelta(days=90), to_ts=None)
    if f == "last_year":
        return _Range(from_ts=now - timedelta(days=365), to_ts=None)
    if f == "last_auction":
        return _Range(from_ts=None, to_ts=None)

    raise ValueError(
        "Invalid filter. Allowed: last_auction, last_week, last_month, last_three_months, last_year, custom"
    )


def get_sales_report(
    *,
    boat_owner_id: str,
    filter_name: str = "last_three_months",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Return sales report for a boat owner.

    Only auctions with non-null `sale` are included (sale is set when delivery is recorded/backfilled).
    Filtering uses auction start_time for the date window.
    """
    limit = int(limit or 50)
    offset = int(offset or 0)
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    if offset < 0:
        offset = 0

    f = (filter_name or "last_three_months").strip().lower()
    range_ = _compute_range(f, from_date, to_date)

    q_search = (search or "").strip()
    has_search = bool(q_search)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Base WHERE clauses (seller + has sale)
        where = ["a.seller_id = %s", "a.sale IS NOT NULL"]
        params: List[Any] = [boat_owner_id]

        # Date window (not for last_auction; that’s handled via LIMIT 1 semantics)
        if f != "last_auction" and range_.from_ts is not None:
            where.append("a.start_time >= %s")
            params.append(range_.from_ts)
        if f != "last_auction" and range_.to_ts is not None:
            where.append("a.start_time < %s")
            params.append(range_.to_ts)

        # Search: boat number, fish name, auction id (covers auction_identifier fallback behavior)
        if has_search:
            where.append("(COALESCE(b.boat_number,'') ILIKE %s OR COALESCE(a.fish_name,'') ILIKE %s OR a.id::text ILIKE %s)")
            like = f"%{q_search}%"
            params.extend([like, like, like])

        where_sql = " AND ".join(where)

        # Total earnings and total record count are computed over the full filtered set (not page).
        cur.execute(
            f"""
            SELECT
                COALESCE(SUM(a.sale), 0) AS total_earning,
                COUNT(*) AS total_records
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total_row = cur.fetchone() or (0, 0)
        total_earning = float(total_row[0] or 0.0)
        total_records = int(total_row[1] or 0)

        # Records query
        if f == "last_auction":
            records_limit = 1
            records_offset = 0
        else:
            records_limit = limit
            records_offset = offset

        cur.execute(
            f"""
            SELECT
                a.id,
                a.fish_name,
                a.auction_type,
                a.start_time,
                a.sale,
                b.boat_number
            FROM auctions a
            LEFT JOIN boat_movements m ON m.id = a.movement_id
            LEFT JOIN bidding_requests br ON br.id = a.bidding_request_id
            LEFT JOIN boats b ON b.id = COALESCE(m.boat_id, br.boat_id) AND b.deleted_at IS NULL
            WHERE {where_sql}
            ORDER BY a.start_time DESC NULLS LAST, a.created_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [records_limit, records_offset]),
        )
        rows = cur.fetchall() or []

        records: List[Dict[str, Any]] = []
        for r in rows:
            auction_id = str(r[0])
            fish_name = r[1] or None
            auction_type_raw = r[2] or "open_box"
            start_time = r[3]
            sale = float(r[4] or 0.0)
            boat_number = r[5]

            records.append(
                {
                    "auction_id": auction_id,
                    "auction_identifier": _auction_identifier(auction_id, boat_number),
                    "boat_number": (str(boat_number).strip() if boat_number else None),
                    "fish_type": fish_name,
                    "auction_type": _auction_type_display(auction_type_raw),
                    "start_time": start_time,
                    "sale": sale,
                }
            )

        return {
            "success": True,
            "total_earning": total_earning,
            "total_records": total_records,
            "filter_applied": {
                "filter": f,
                "from_date": from_date,
                "to_date": to_date,
            },
            "records": records,
        }
    finally:
        cur.close()
        conn.close()

