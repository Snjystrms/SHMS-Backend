"""Service layer for agent bidding requests."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from zoneinfo import ZoneInfo

from app.db.session import get_db_connection

IST = ZoneInfo("Asia/Kolkata")
IST_TIME_FMT = "%I:%M %p, %d %b %Y"


def create_bidding_request(
    boat_id: str,
    agent_id: str,
    note: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Agent sends a bidding request for an arrived boat.
    Validates: boat exists, boat has an owner, no duplicate pending request.
    Returns (request_dict, None) on success or (None, error_message).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, boat_owner_id, boat_number, boat_name FROM boats WHERE id = %s AND deleted_at IS NULL",
            (boat_id,),
        )
        boat = cur.fetchone()
        if not boat:
            return None, "Boat not found"

        boat_owner_id = boat[1]
        if not boat_owner_id:
            return None, "This boat has no registered owner"

        boat_number = boat[2] or ""
        boat_name = boat[3] or ""

        # Prevent duplicate pending request from the same agent for the same boat
        cur.execute(
            """
            SELECT id FROM bidding_requests
            WHERE boat_id = %s AND agent_id = %s AND status = 'pending'
            """,
            (boat_id, agent_id),
        )
        if cur.fetchone():
            return None, "You already have a pending bidding request for this boat"

        request_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO bidding_requests (id, boat_id, agent_id, boat_owner_id, note)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (request_id, boat_id, agent_id, str(boat_owner_id), note),
        )
        row = cur.fetchone()
        conn.commit()

        created_at = row[1]
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at_ist = created_at.astimezone(IST) if created_at else None

        cur.execute("SELECT name FROM users WHERE id = %s", (agent_id,))
        agent_row = cur.fetchone()
        agent_name = agent_row[0] if agent_row else ""

        return {
            "id": request_id,
            "boat_id": str(boat_id),
            "boat_number": boat_number,
            "boat_name": boat_name,
            "agent_id": str(agent_id),
            "agent_name": agent_name,
            "boat_owner_id": str(boat_owner_id),
            "status": "pending",
            "note": note,
            "created_at": created_at_ist.strftime(IST_TIME_FMT) if created_at_ist else "",
        }, None
    except Exception as e:
        conn.rollback()
        print(f"Error creating bidding request: {e}")
        return None, str(e)
    finally:
        cur.close()
        conn.close()


def list_bidding_requests_for_owner(
    boat_owner_id: str,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List bidding requests addressed to this boat owner."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT
                br.id, br.boat_id, b.boat_number, b.boat_name,
                br.agent_id, u.name AS agent_name,
                br.status, br.note, br.created_at
            FROM bidding_requests br
            JOIN boats b ON b.id = br.boat_id AND b.deleted_at IS NULL
            JOIN users u ON u.id = br.agent_id
            WHERE br.boat_owner_id = %s
        """
        params: list = [boat_owner_id]
        if status_filter and status_filter in ("pending", "approved", "rejected"):
            query += " AND br.status = %s"
            params.append(status_filter)
        query += " ORDER BY br.created_at DESC"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            created = r[8]
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            created_ist = created.astimezone(IST) if created else None
            results.append({
                "id": str(r[0]),
                "boat_id": str(r[1]),
                "boat_number": r[2] or "",
                "boat_name": r[3] or "",
                "agent_id": str(r[4]),
                "agent_name": r[5] or "",
                "status": r[6],
                "note": r[7],
                "created_at": created_ist.strftime(IST_TIME_FMT) if created_ist else "",
            })
        return results
    except Exception as e:
        print(f"Error listing bidding requests: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def list_bidding_requests_for_agent(
    agent_id: str,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List bidding requests sent by this agent."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT
                br.id, br.boat_id, b.boat_number, b.boat_name,
                br.agent_id, u.name AS agent_name,
                br.status, br.note, br.created_at
            FROM bidding_requests br
            JOIN boats b ON b.id = br.boat_id AND b.deleted_at IS NULL
            JOIN users u ON u.id = br.agent_id
            WHERE br.agent_id = %s
        """
        params: list = [agent_id]
        if status_filter and status_filter in ("pending", "approved", "rejected"):
            query += " AND br.status = %s"
            params.append(status_filter)
        query += " ORDER BY br.created_at DESC"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            created = r[8]
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            created_ist = created.astimezone(IST) if created else None
            results.append({
                "id": str(r[0]),
                "boat_id": str(r[1]),
                "boat_number": r[2] or "",
                "boat_name": r[3] or "",
                "agent_id": str(r[4]),
                "agent_name": r[5] or "",
                "status": r[6],
                "note": r[7],
                "created_at": created_ist.strftime(IST_TIME_FMT) if created_ist else "",
            })
        return results
    except Exception as e:
        print(f"Error listing agent bidding requests: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def respond_to_bidding_request(
    request_id: str,
    boat_owner_id: str,
    new_status: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Boat owner approves or rejects a bidding request.
    Returns (updated_request, None) or (None, error).
    """
    if new_status not in ("approved", "rejected"):
        return None, "Status must be 'approved' or 'rejected'"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT br.id, br.boat_id, br.agent_id, br.status,
                   b.boat_number, b.boat_name, u.name AS agent_name, br.note
            FROM bidding_requests br
            JOIN boats b ON b.id = br.boat_id
            JOIN users u ON u.id = br.agent_id
            WHERE br.id = %s AND br.boat_owner_id = %s
            """,
            (request_id, boat_owner_id),
        )
        row = cur.fetchone()
        if not row:
            return None, "Bidding request not found"

        current_status = row[3]
        if current_status != "pending":
            return None, f"Request already {current_status}"

        cur.execute(
            """
            UPDATE bidding_requests
            SET status = %s, responded_at = NOW(), updated_at = NOW()
            WHERE id = %s
            RETURNING created_at
            """,
            (new_status, request_id),
        )
        updated = cur.fetchone()
        conn.commit()

        created = updated[0] if updated else None
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        created_ist = created.astimezone(IST) if created else None

        return {
            "id": str(row[0]),
            "boat_id": str(row[1]),
            "boat_number": row[4] or "",
            "boat_name": row[5] or "",
            "agent_id": str(row[2]),
            "agent_name": row[6] or "",
            "status": new_status,
            "note": row[7],
            "created_at": created_ist.strftime(IST_TIME_FMT) if created_ist else "",
        }, None
    except Exception as e:
        conn.rollback()
        print(f"Error responding to bidding request: {e}")
        return None, str(e)
    finally:
        cur.close()
        conn.close()
