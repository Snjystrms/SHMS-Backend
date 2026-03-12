"""Trip status service: boat movement tracking (departure, arrival, partial arrival)."""
import uuid
from datetime import datetime, timezone, timedelta
from threading import Lock
from typing import Optional, Dict, Any, Tuple, List
from zoneinfo import ZoneInfo
from app.db.session import get_db_connection

_DASHBOARD_COUNTS_CACHE_TTL_SECONDS = 10
_dashboard_counts_cache_lock = Lock()
_dashboard_counts_cache: Dict[str, Any] = {
    "expires_at": datetime.min.replace(tzinfo=timezone.utc),
    "data": None,
}


def get_boat_trip_status(boat_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns boat trip status: docked | sailing | arrived | partial_arrival.
    - docked: No departure record
    - sailing: Latest movement is departure, no arrival after it
    - arrived: Latest movement is arrival
    - partial_arrival: Latest movement is partial_arrival
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT b.id, b.boat_number, b.boat_name, b.boat_type, b.harbor_name
            FROM boats b WHERE b.id = %s AND b.deleted_at IS NULL
            """,
            (boat_id,),
        )
        boat_row = cur.fetchone()
        if not boat_row:
            return None

        boat_id_val, boat_number, _, boat_type, harbor_name = boat_row

        cur.execute(
            """
            SELECT id, movement_type, movement_at, port_name, crew_count, image_url
            FROM boat_movements
            WHERE boat_id = %s
            ORDER BY movement_at DESC
            LIMIT 10
            """,
            (boat_id,),
        )
        movements = cur.fetchall()

        if not movements:
            return {
                "boat_id": str(boat_id_val),
                "boat_number": boat_number or "",
                "trip_status": "docked",
                "departure_details": None,
                "has_open_departure": False,
                "last_movement_at": None,
                "latest_movement_id": None,
            }

        latest_id, latest_type, latest_at, port_name, crew_count, image_url = movements[0]

        if latest_type == "departure":
            trip_status = "sailing"
            departure_details = {
                "departure_at": latest_at,
                "from_port": port_name or harbor_name or "Unknown",
                "vessel_type": boat_type,
                "crew_count": crew_count,
                "status_label": "Sailing",
                "image_url": image_url,
            }
            has_open = True
        elif latest_type == "arrival":
            trip_status = "arrived"
            departure_details = None
            has_open = False
        elif latest_type == "partial_arrival":
            trip_status = "partial_arrival"
            departure_details = None
            has_open = False
        else:
            trip_status = "docked"
            departure_details = None
            has_open = False

        result = {
            "boat_id": str(boat_id_val),
            "boat_number": boat_number or "",
            "trip_status": trip_status,
            "departure_details": departure_details,
            "has_open_departure": has_open,
            "last_movement_at": latest_at,
            "last_movement_image_url": image_url,
            "latest_movement_id": str(latest_id) if latest_id else None,
        }
        if has_open and latest_id:
            result["open_departure_movement_id"] = str(latest_id)
        return result
    except Exception as e:
        print(f"Error fetching boat trip status: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def get_movement_history(
    movement_type: str,
    date_filter: str,
) -> List[Dict[str, Any]]:
    """
    Return list of movements filtered by type and date range.
    Used by history screens (e.g. departure history with Today / 7 days / month filters).
    """
    if movement_type not in ("departure", "arrival", "partial_arrival"):
        raise ValueError("Invalid movement_type")

    now = datetime.now(timezone.utc)
    if date_filter == "today":
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    elif date_filter == "last_7_days":
        start = now - timedelta(days=7)
    elif date_filter == "last_30_days":
        start = now - timedelta(days=30)
    else:
        raise ValueError("Invalid date_filter")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                m.id,
                m.boat_id,
                b.boat_number,
                b.boat_name,
                m.movement_type,
                m.movement_at,
                m.port_name,
                m.crew_count,
                m.image_url
            FROM boat_movements m
            JOIN boats b ON b.id = m.boat_id AND b.deleted_at IS NULL
            WHERE m.movement_type = %s
              AND m.movement_at >= %s
            ORDER BY m.movement_at DESC
            LIMIT 200
            """,
            (movement_type, start),
        )
        rows = cur.fetchall()
        return [
            {
                "movement_id": str(r[0]),
                "boat_id": str(r[1]),
                "boat_number": r[2] or "",
                "boat_name": r[3],
                "movement_type": r[4],
                "movement_at": r[5],
                "port_name": r[6],
                "crew_count": r[7],
                "image_url": r[8],
            }
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()


def get_dashboard_today_counts() -> Dict[str, Any]:
    """
    Return today's counts for port officer dashboard: departures, arrivals,
    crew registrations (new crew created today), crew verifications (crew scanned at departure today).
    """
    now = datetime.now(timezone.utc)
    with _dashboard_counts_cache_lock:
        cached = _dashboard_counts_cache["data"]
        expires_at = _dashboard_counts_cache["expires_at"]
        if cached and now < expires_at:
            return dict(cached)

    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COALESCE((
                    SELECT COUNT(*)
                    FROM boat_movements
                    WHERE movement_type = 'departure'
                      AND movement_at >= %s
                      AND movement_at < %s
                ), 0) AS departures,
                COALESCE((
                    SELECT COUNT(*)
                    FROM boat_movements
                    WHERE movement_type = 'arrival'
                      AND movement_at >= %s
                      AND movement_at < %s
                ), 0) AS arrivals,
                COALESCE((
                    SELECT COUNT(*)
                    FROM crew_members
                    WHERE created_at >= %s
                      AND created_at < %s
                      AND deleted_at IS NULL
                ), 0) AS crew_registration,
                COALESCE((
                    SELECT COUNT(*)
                    FROM boat_movement_crew bmc
                    JOIN boat_movements m
                      ON m.id = bmc.movement_id
                     AND m.movement_type = 'departure'
                    WHERE m.movement_at >= %s
                      AND m.movement_at < %s
                ), 0) AS crew_verification
            """,
            (start, end, start, end, start, end, start, end),
        )
        row = cur.fetchone() or (0, 0, 0, 0)
        departures, arrivals, crew_registration, crew_verification = row

        result = {
            "departures": departures,
            "arrivals": arrivals,
            "crew_registration": crew_registration,
            "crew_verification": crew_verification,
            "updated_at": now,
        }
        with _dashboard_counts_cache_lock:
            _dashboard_counts_cache["data"] = result
            _dashboard_counts_cache["expires_at"] = now + timedelta(
                seconds=_DASHBOARD_COUNTS_CACHE_TTL_SECONDS
            )
        return result
    finally:
        cur.close()
        conn.close()


def get_agent_dashboard_arrivals(agent_id: str) -> Dict[str, Any]:
    """
    Agent dashboard: today's arrived boats count + all arrived boats (today, IST).
    "Arrived" is derived from boat_movements.movement_type = 'arrival'.
    Includes bidding_request_status for each boat (this agent's most recent request).
    """
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(timezone.utc).astimezone(ist)
    today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_ist = today_start_ist + timedelta(days=1)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                b.id,
                b.boat_number,
                b.boat_name,
                m.movement_at,
                br.status AS bidding_request_status,
                COUNT(*) OVER() AS arrived_count
            FROM boat_movements m
            JOIN boats b ON b.id = m.boat_id AND b.deleted_at IS NULL
            LEFT JOIN (
                SELECT DISTINCT ON (boat_id) boat_id, status
                FROM bidding_requests
                WHERE agent_id = %s
                ORDER BY boat_id, created_at DESC
            ) br ON br.boat_id = b.id
            WHERE m.movement_type = 'arrival'
              AND m.movement_at >= %s
              AND m.movement_at < %s
            ORDER BY m.movement_at DESC
            """,
            (agent_id, today_start_ist, today_end_ist),
        )
        rows = cur.fetchall()
        arrived_count = int(rows[0][5]) if rows else 0
        boats = [
            {
                "boat_id": str(r[0]),
                "boat_number": r[1] or "",
                "boat_name": r[2] or "",
                "boat_status": "Arrived",
                "time": (
                    (r[3].replace(tzinfo=timezone.utc) if r[3].tzinfo is None else r[3]).astimezone(ist).strftime("%I:%M %p")
                    if r[3]
                    else None
                ),
                "bidding_request_status": r[4] if len(r) > 4 and r[4] else None,
            }
            for r in rows
        ]

        return {
            "arrived_boats_count": arrived_count,
            "arrived_boats": boats,
            "updated_at": now_ist,
        }
    finally:
        cur.close()
        conn.close()


def get_boat_owner_dashboard(boat_owner_id: str) -> Dict[str, Any]:
    """
    Boat owner dashboard: total boats, in-sea count, and today's arrived boats
    pending auction with per-boat pending bidding request counts.
    """
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(timezone.utc).astimezone(ist)
    today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_ist = today_start_ist + timedelta(days=1)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1 + 2. Total boats and in-sea boats from latest movement per owned boat.
        cur.execute(
            """
            WITH owned_boats AS (
                SELECT id
                FROM boats
                WHERE boat_owner_id = %s
                  AND deleted_at IS NULL
            ),
            latest_movement AS (
                SELECT DISTINCT ON (m.boat_id)
                    m.boat_id,
                    m.movement_type
                FROM boat_movements m
                JOIN owned_boats ob ON ob.id = m.boat_id
                ORDER BY m.boat_id, m.movement_at DESC
            )
            SELECT
                (SELECT COUNT(*) FROM owned_boats) AS total_boats,
                (SELECT COUNT(*) FROM latest_movement WHERE movement_type = 'departure') AS in_sea
            """,
            (boat_owner_id,),
        )
        total_boats, in_sea = cur.fetchone() or (0, 0)

        # 3. Latest arrived boats today with pending bidding request counts.
        cur.execute(
            """
            WITH owned_boats AS (
                SELECT id, boat_number, boat_name
                FROM boats
                WHERE boat_owner_id = %s
                  AND deleted_at IS NULL
            ),
            latest_arrivals AS (
                SELECT DISTINCT ON (m.boat_id)
                    m.id AS movement_id,
                    m.boat_id,
                    m.movement_at
                FROM boat_movements m
                JOIN owned_boats ob ON ob.id = m.boat_id
                WHERE m.movement_type = 'arrival'
                  AND m.movement_at >= %s
                  AND m.movement_at < %s
                ORDER BY m.boat_id, m.movement_at DESC
            ),
            pending_request_counts AS (
                SELECT br.boat_id, COUNT(*) AS cnt
                FROM bidding_requests br
                JOIN owned_boats ob ON ob.id = br.boat_id
                WHERE br.status = 'pending'
                GROUP BY br.boat_id
            )
            SELECT
                la.movement_id,
                ob.id,
                ob.boat_number,
                ob.boat_name,
                la.movement_at,
                COALESCE(prc.cnt, 0) AS pending_requests
            FROM latest_arrivals la
            JOIN owned_boats ob ON ob.id = la.boat_id
            LEFT JOIN pending_request_counts prc ON prc.boat_id = ob.id
            ORDER BY la.movement_at DESC
            """,
            (boat_owner_id, today_start_ist, today_end_ist),
        )
        rows = cur.fetchall()
        pending_auctions = []
        for r in rows:
            arrival_dt = r[4]
            if arrival_dt and arrival_dt.tzinfo is None:
                arrival_dt = arrival_dt.replace(tzinfo=timezone.utc)
            arrival_ist = arrival_dt.astimezone(ist) if arrival_dt else None
            pending_auctions.append({
                "boat_id": str(r[1]),
                "boat_number": r[2] or "",
                "boat_name": r[3] or "",
                "status": "Arrived",
                "arrival_time": arrival_ist.strftime("%I:%M %p") if arrival_ist else "",
                "pending_bidding_requests_count": int(r[5]),
                "latest_movement_id": str(r[0]) if r[0] else None,
            })

        return {
            "quick_activity": {
                "total_boats": int(total_boats),
                "in_sea": int(in_sea),
            },
            "pending_auctions": pending_auctions,
            "updated_at": now_ist,
        }
    except Exception as e:
        print(f"Error fetching boat owner dashboard: {e}")
        return {
            "quick_activity": {"total_boats": 0, "in_sea": 0},
            "pending_auctions": [],
            "updated_at": now_ist,
        }
    finally:
        cur.close()
        conn.close()


def get_open_departure_movement(boat_id: str) -> Optional[Dict[str, Any]]:
    """
    Return the open (unclosed) departure movement for this boat, if any.
    Used for arrival crew/inventory checks. Returns None if boat is not sailing.
    """
    status_data = get_boat_trip_status(boat_id)
    if not status_data or not status_data.get("has_open_departure"):
        return None
    movement_id = status_data.get("open_departure_movement_id")
    if not movement_id:
        return None
    return get_departure_movement_by_id(movement_id, boat_id=boat_id)


def get_departure_movement_by_id(movement_id: str, boat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Return the departure movement by id. If boat_id is given, validate it matches.
    Used when updating by movement_id (set crew/inventory — only allowed for open departure).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if boat_id:
            cur.execute(
                """
                SELECT id, boat_id, movement_type, movement_at, port_name, crew_count, image_url
                FROM boat_movements
                WHERE id = %s AND boat_id = %s AND movement_type = 'departure'
                """,
                (movement_id, boat_id),
            )
        else:
            cur.execute(
                """
                SELECT id, boat_id, movement_type, movement_at, port_name, crew_count, image_url
                FROM boat_movements
                WHERE id = %s AND movement_type = 'departure'
                """,
                (movement_id,),
            )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "boat_id": str(row[1]),
            "movement_type": row[2],
            "movement_at": row[3],
            "port_name": row[4],
            "crew_count": row[5],
            "image_url": row[6],
        }
    finally:
        cur.close()
        conn.close()


def get_trip_movement_by_id(movement_id: str, boat_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Return the trip movement by id (departure or arrival — same id after arrival is logged).
    Use for arrival crew scan, arrival inventory check, and fetching inventory for a trip.
    If boat_id is given, validate it matches.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if boat_id:
            cur.execute(
                """
                SELECT id, boat_id, movement_type, movement_at, port_name, crew_count, image_url
                FROM boat_movements
                WHERE id = %s AND boat_id = %s AND movement_type IN ('departure', 'arrival')
                """,
                (movement_id, boat_id),
            )
        else:
            cur.execute(
                """
                SELECT id, boat_id, movement_type, movement_at, port_name, crew_count, image_url
                FROM boat_movements
                WHERE id = %s AND movement_type IN ('departure', 'arrival')
                """,
                (movement_id,),
            )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "boat_id": str(row[1]),
            "movement_type": row[2],
            "movement_at": row[3],
            "port_name": row[4],
            "crew_count": row[5],
            "image_url": row[6],
        }
    finally:
        cur.close()
        conn.close()


def get_movement_with_departure_arrival(
    movement_id: str, boat_id: str
) -> Optional[Dict[str, Any]]:
    """
    Return movement with departure_at and arrival info for boat owner trip details.
    For arrival: has departure_at, movement_at (arrival), port_name (to_port).
    For partial_arrival: has movement_at, port_name, partial_arrival_reason, partial_arrival_details.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT m.id, m.boat_id, m.movement_type, m.movement_at, m.departure_at,
                   m.port_name, m.crew_count, m.image_url, m.partial_arrival_reason,
                   m.partial_arrival_details, b.harbor_name
            FROM boat_movements m
            JOIN boats b ON b.id = m.boat_id AND b.deleted_at IS NULL
            WHERE m.id = %s AND m.boat_id = %s
              AND m.movement_type IN ('departure', 'arrival', 'partial_arrival')
            """,
            (movement_id, boat_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "boat_id": str(row[1]),
            "movement_type": row[2],
            "movement_at": row[3],
            "departure_at": row[4],
            "port_name": row[5],
            "crew_count": row[6],
            "image_url": row[7],
            "partial_arrival_reason": row[8],
            "partial_arrival_details": row[9],
            "harbor_name": row[10],
        }
    finally:
        cur.close()
        conn.close()


def get_departure_crew_with_details(movement_id: str) -> List[Dict[str, Any]]:
    """Return list of crew members (id, name, etc.) attached to this departure movement."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT cm.id, cm.name, cm.aadhaar_number, cm.phone, cm.is_pilot, bmc.crop_id
            FROM boat_movement_crew bmc
            JOIN crew_members cm ON cm.id = bmc.crew_member_id AND cm.deleted_at IS NULL
            WHERE bmc.movement_id = %s
            ORDER BY cm.name
            """,
            (movement_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "name": r[1] or "",
                "aadhaar_number": r[2],
                "phone": r[3],
                "is_pilot": bool(r[4]) if r[4] is not None else False,
                "crop_id": r[5],
            }
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()


def get_departure_inventory(movement_id: str) -> Optional[Dict[str, Any]]:
    """Return inventory record for this departure movement, or None."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT diesel_liters, ice_blocks, fishing_net_count, plastic_bottle_count, plastic_bag_count
            FROM boat_movement_inventory
            WHERE movement_id = %s
            LIMIT 1
            """,
            (movement_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "diesel_liters": row[0],
            "ice_blocks": row[1],
            "fishing_net_count": row[2],
            "plastic_bottle_count": row[3],
            "plastic_bag_count": row[4],
        }
    finally:
        cur.close()
        conn.close()


def create_boat_movement(
    boat_id: str,
    movement_type: str,
    movement_at: Optional[datetime],
    logged_by_user_id: Optional[str],
    partial_arrival_reason: Optional[str],
    partial_arrival_details: Optional[str],
    image_url: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Create or update a boat movement record.
    - Departure: always creates a new movement (new id).
    - Arrival: updates the existing open departure row (same movement id); does not create a new row.
    - Partial arrival: creates a new movement (new id).
    Returns (movement_dict, None) on success, or (None, error_message) on validation/DB error.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM boats WHERE id = %s AND deleted_at IS NULL",
            (boat_id,),
        )
        if not cur.fetchone():
            return None, "Boat not found"

        if movement_type == "arrival":
            status_data = get_boat_trip_status(boat_id)
            if not status_data or not status_data.get("has_open_departure"):
                return None, _ERR_ARRIVAL_NEEDS_DEPARTURE
            # Update the existing departure row to arrival (same movement_id)
            open_id = status_data.get("open_departure_movement_id")
            if not open_id:
                return None, _ERR_ARRIVAL_NEEDS_DEPARTURE
            movement_at_val = movement_at or datetime.now(timezone.utc)
            cur.execute(
                """
                UPDATE boat_movements
                SET departure_at = COALESCE(departure_at, movement_at),
                    movement_at = %s,
                    movement_type = 'arrival',
                    image_url = COALESCE(%s, image_url),
                    updated_at = NOW()
                WHERE id = %s AND boat_id = %s AND movement_type = 'departure'
                RETURNING id, boat_id, movement_type, movement_at,
                          partial_arrival_reason, partial_arrival_details, image_url
                """,
                (movement_at_val, image_url, open_id, boat_id),
            )
            row = cur.fetchone()
            if not row:
                return None, _ERR_ARRIVAL_NEEDS_DEPARTURE
            conn.commit()
            return {
                "id": str(row[0]),
                "boat_id": str(row[1]),
                "movement_type": row[2],
                "movement_at": row[3],
                "partial_arrival_reason": row[4],
                "partial_arrival_details": row[5],
                "image_url": row[6],
            }, None

        if movement_type == "partial_arrival" and not partial_arrival_reason:
            return None, "partial_arrival_reason is required for partial_arrival"

        movement_at_val = movement_at or datetime.now(timezone.utc)
        movement_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO boat_movements (
                id, boat_id, movement_type, movement_at,
                logged_by_user_id, partial_arrival_reason, partial_arrival_details, image_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                movement_id,
                boat_id,
                movement_type,
                movement_at_val,
                logged_by_user_id,
                partial_arrival_reason,
                partial_arrival_details,
                image_url,
            ),
        )
        conn.commit()

        return {
            "id": movement_id,
            "boat_id": boat_id,
            "movement_type": movement_type,
            "movement_at": movement_at_val,
            "partial_arrival_reason": partial_arrival_reason,
            "partial_arrival_details": partial_arrival_details,
            "image_url": image_url,
        }, None
    except Exception as e:
        conn.rollback()
        print(f"Error creating boat movement: {e}")
        return None, str(e)
    finally:
        cur.close()
        conn.close()


_ERR_ARRIVAL_NEEDS_DEPARTURE = "No departure record found. Arrival requires an open departure."


def _get_departure_movement_for_boat(
    cur, boat_id: str, movement_id: str
) -> Optional[Tuple[str, str]]:
    """
    Ensure the given movement_id exists for this boat and is a departure.
    Returns (movement_id, boat_id) or None.
    """
    cur.execute(
        """
        SELECT id, boat_id
        FROM boat_movements
        WHERE id = %s AND boat_id = %s AND movement_type = 'departure'
        """,
        (movement_id, boat_id),
    )
    row = cur.fetchone()
    if not row:
        return None
    return row[0], str(row[1])


def _get_departure_movement_by_id(cur, movement_id: str) -> Optional[Tuple[str, str]]:
    """
    Ensure the given movement_id exists and is a departure. Returns (movement_id, boat_id) or None.
    """
    cur.execute(
        """
        SELECT id, boat_id
        FROM boat_movements
        WHERE id = %s AND movement_type = 'departure'
        """,
        (movement_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return str(row[0]), str(row[1])


def set_boat_movement_crew(
    movement_id: str,
    crew_member_ids: List[str],
    unidentified_count: int,
    crew_crop_ids: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Attach crew list to a specific departure movement.
    Overwrites any existing crew entries for this movement and updates crew_count.
    crew_crop_ids: optional mapping of crew_member_id -> crop_id for face image display.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        key = _get_departure_movement_by_id(cur, movement_id)
        if not key:
            return None, "Departure movement not found"
        _movement_id, boat_id = key

        # Remove existing crew assignments for this movement
        cur.execute(
            "DELETE FROM boat_movement_crew WHERE movement_id = %s",
            (movement_id,),
        )

        crew_crop_ids = crew_crop_ids or {}
        unique_ids = list(dict.fromkeys(crew_member_ids)) if crew_member_ids else []
        for cid in unique_ids:
            crop_id = crew_crop_ids.get(cid)
            cur.execute(
                """
                INSERT INTO boat_movement_crew (id, movement_id, crew_member_id, crop_id)
                VALUES (%s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), movement_id, cid, crop_id),
            )

        total_count = len(unique_ids) + max(unidentified_count or 0, 0)

        # Update crew_count on boat_movements for quick status lookup
        cur.execute(
            """
            UPDATE boat_movements
            SET crew_count = %s
            WHERE id = %s
            """,
            (total_count, movement_id),
        )

        conn.commit()

        return {
            "movement_id": movement_id,
            "boat_id": boat_id,
            "total_crew_count": total_count,
            "identified_crew_ids": unique_ids,
            "unidentified_count": max(unidentified_count or 0, 0),
        }, None
    except Exception as e:
        conn.rollback()
        print(f"Error setting boat movement crew: {e}")
        return None, str(e)
    finally:
        cur.close()
        conn.close()


def set_boat_movement_inventory(
    movement_id: str,
    diesel_liters: Optional[float],
    ice_blocks: Optional[int],
    fishing_net_count: Optional[int],
    plastic_bottle_count: Optional[int],
    plastic_bag_count: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Attach inventory (diesel, ice, nets, plastics) to a specific departure movement.
    Overwrites any existing inventory record for this movement.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        key = _get_departure_movement_by_id(cur, movement_id)
        if not key:
            return None, "Departure movement not found"
        _movement_id, boat_id = key

        # Remove any existing inventory row for this movement
        cur.execute(
            "DELETE FROM boat_movement_inventory WHERE movement_id = %s",
            (movement_id,),
        )

        cur.execute(
            """
            INSERT INTO boat_movement_inventory (
                id,
                movement_id,
                diesel_liters,
                ice_blocks,
                fishing_net_count,
                plastic_bottle_count,
                plastic_bag_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                movement_id,
                diesel_liters,
                ice_blocks,
                fishing_net_count,
                plastic_bottle_count,
                plastic_bag_count,
            ),
        )

        conn.commit()

        return {
            "movement_id": movement_id,
            "boat_id": boat_id,
            "diesel_liters": diesel_liters,
            "ice_blocks": ice_blocks,
            "fishing_net_count": fishing_net_count,
            "plastic_bottle_count": plastic_bottle_count,
            "plastic_bag_count": plastic_bag_count,
        }, None
    except Exception as e:
        conn.rollback()
        print(f"Error setting boat movement inventory: {e}")
        return None, str(e)
    finally:
        cur.close()
        conn.close()


def get_scanned_crew_history(
    officer_user_id: Optional[str],
    date_filter: str,
    is_register: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Return list of crew scanned (attached to departures) for movements logged by an officer.
    Used by the Crew Scanned history screen.
    """
    now = datetime.now(timezone.utc)
    if date_filter == "today":
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    elif date_filter == "last_7_days":
        start = now - timedelta(days=7)
    elif date_filter == "last_15_days":
        start = now - timedelta(days=15)
    else:
        raise ValueError("Invalid date_filter")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        params: List[Any] = [start]
        clauses: List[str] = []
        if officer_user_id:
            clauses.append("m.logged_by_user_id = %s")
            params.append(officer_user_id)
        if is_register is not None:
            clauses.append("cm.is_register = %s")
            params.append(is_register)

        where_extra = ""
        if clauses:
            where_extra = " AND " + " AND ".join(clauses)

        cur.execute(
            f"""
            SELECT
                cm.id AS crew_id,
                cm.name AS crew_name,
                cm.aadhaar_number,
                cm.phone,
                cm.emergency_contact_number,
                cm.is_pilot,
                b.id AS boat_id,
                b.boat_name,
                b.boat_number,
                m.movement_at,
                bmc.crop_id
            FROM boat_movements m
            JOIN boat_movement_crew bmc ON bmc.movement_id = m.id
            JOIN crew_members cm ON cm.id = bmc.crew_member_id AND cm.deleted_at IS NULL
            JOIN boats b ON b.id = m.boat_id AND b.deleted_at IS NULL
            WHERE m.movement_type = 'departure'
              AND m.movement_at >= %s
              {where_extra}
            ORDER BY m.movement_at DESC
            LIMIT 200
            """,
            tuple(params),
        )
        rows = cur.fetchall()
        return [
            {
                "crew_id": str(r[0]),
                "crew_name": r[1] or "",
                "aadhaar_number": r[2],
                "phone_number": r[3],
                "emergency_contact_number": r[4],
                "is_pilot": bool(r[5]) if r[5] is not None else False,
                "boat_id": str(r[6]),
                "boat_name": r[7],
                "boat_number": r[8],
                "movement_at": r[9].isoformat() if r[9] else None,
                "image_url": f"/uploads/crew-crops/{r[10]}.png" if r[10] else None,
            }
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()


def save_unidentified_crew_member(movement_id: str, crop_image_url: Optional[str] = None) -> str:
    """Insert an unidentified crew member for an arrival scan. Returns the new row id."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        row_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO unidentified_crew_members (id, movement_id, crop_image_url)
            VALUES (%s, %s, %s)
            """,
            (row_id, movement_id, crop_image_url),
        )
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
