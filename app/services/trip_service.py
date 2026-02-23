"""Trip status service: boat movement tracking (departure, arrival, partial arrival)."""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
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
            SELECT movement_type, movement_at, port_name, crew_count
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

        latest_type, latest_at, port_name, crew_count = movements[0]

        if latest_type == "departure":
            trip_status = "sailing"
            departure_details = {
                "departure_at": latest_at,
                "from_port": port_name or harbor_name or "Unknown",
                "vessel_type": boat_type,
                "crew_count": crew_count,
                "status_label": "Sailing",
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

        return {
            "boat_id": str(boat_id_val),
            "boat_number": boat_number or "",
            "trip_status": trip_status,
            "departure_details": departure_details,
            "has_open_departure": has_open,
            "last_movement_at": latest_at,
        }
    except Exception as e:
        print(f"Error fetching boat trip status: {e}")
        return None
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
                logged_by_user_id, partial_arrival_reason, partial_arrival_details
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                movement_id,
                boat_id,
                movement_type,
                movement_at_val,
                logged_by_user_id,
                partial_arrival_reason,
                partial_arrival_details,
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
        }, None
    except Exception as e:
        conn.rollback()
        print(f"Error creating boat movement: {e}")
        return None, str(e)
    finally:
        cur.close()
        conn.close()
