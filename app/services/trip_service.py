"""Trip status service: boat movement tracking (departure, arrival, partial arrival)."""
import uuid
from datetime import datetime, timezone
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
    Used when updating by movement_id (arrival crew/inventory checks).
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
    Create a boat movement record. Returns (movement_dict, None) on success,
    or (None, error_message) on validation/DB error.
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
                return None, "No departure record found. Arrival requires an open departure."

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
