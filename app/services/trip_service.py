"""Trip status service: boat movement tracking (departure, arrival, partial arrival)."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List
from app.db.session import get_db_connection


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
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Departures today
        cur.execute(
            """
            SELECT COUNT(*) FROM boat_movements
            WHERE movement_type = 'departure' AND movement_at >= %s
            """,
            (start,),
        )
        departures = cur.fetchone()[0] or 0

        # Arrivals today (full arrival only; partial_arrival is separate if needed)
        cur.execute(
            """
            SELECT COUNT(*) FROM boat_movements
            WHERE movement_type = 'arrival' AND movement_at >= %s
            """,
            (start,),
        )
        arrivals = cur.fetchone()[0] or 0

        # Crew registrations today (new crew_members created today)
        cur.execute(
            """
            SELECT COUNT(*) FROM crew_members
            WHERE created_at >= %s AND deleted_at IS NULL
            """,
            (start,),
        )
        crew_registration = cur.fetchone()[0] or 0

        # Crew verifications today (crew attached to departures that happened today)
        cur.execute(
            """
            SELECT COUNT(*) FROM boat_movement_crew bmc
            JOIN boat_movements m ON m.id = bmc.movement_id AND m.movement_type = 'departure'
            WHERE m.movement_at >= %s
            """,
            (start,),
        )
        crew_verification = cur.fetchone()[0] or 0

        return {
            "departures": departures,
            "arrivals": arrivals,
            "crew_registration": crew_registration,
            "crew_verification": crew_verification,
            "updated_at": now,
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


def get_departure_crew_with_details(movement_id: str) -> List[Dict[str, Any]]:
    """Return list of crew members (id, name, etc.) attached to this departure movement."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT cm.id, cm.name, cm.aadhaar_number, cm.phone, cm.is_pilot
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
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Attach crew list to a specific departure movement.
    Overwrites any existing crew entries for this movement and updates crew_count.
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

        unique_ids = list(dict.fromkeys(crew_member_ids)) if crew_member_ids else []
        for cid in unique_ids:
            cur.execute(
                """
                INSERT INTO boat_movement_crew (id, movement_id, crew_member_id)
                VALUES (%s, %s, %s)
                """,
                (str(uuid.uuid4()), movement_id, cid),
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
                m.movement_at
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
            }
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()
