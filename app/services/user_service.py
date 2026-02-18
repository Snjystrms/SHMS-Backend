import uuid
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from app.schemas.user import UserCreate, UserUpdate
from app.db.session import get_db_connection

def get_user_by_identifier(identifier: str):
    """Fetch a user by their email address or phone number."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.name, u.email, u.password, u.role_id, r.name as role_name 
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE (u.email = %s OR u.phone = %s) AND u.deleted_at IS NULL
            """,
            (identifier, identifier)
        )
        row = cur.fetchone()
        if row:
            return {
                "id": str(row[0]),
                "name": row[1],
                "email": row[2],
                "password": row[3],
                "role_id": row[4],
                "role": row[5]
            }
        return None
    except Exception as e:
        print(f"Error fetching user by identifier: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def update_user_password(user_id: str, hashed_password: str):
    """Update a user's password with a new hash."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET password = %s, updated_at = NOW() WHERE id = %s",
            (hashed_password, user_id)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error updating user password: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_role_id_by_name(role_name: str):
    """Fetch role ID by role name."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error fetching role ID: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def create_user(user_data: dict, role_id: int):
    """Create a new user in the database."""
    user_id = str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (id, name, email, phone, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                user_id,
                user_data["name"],
                user_data.get("email") or None,
                user_data["phone"],
                role_id
            )
        )
        conn.commit()
        return user_id
    except Exception as e:
        conn.rollback()
        print(f"Error creating user: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def create_officer_user(user_data: dict, role_id: int):
    """Create a new user in the database."""
    user_id = str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (id, name, email, phone, password, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                user_id,
                user_data["name"],
                user_data.get("email") or None,
                user_data["phone"],
                user_data["password"],
                role_id
            )
        )
        conn.commit()
        return user_id
    except Exception as e:
        conn.rollback()
        print(f"Error creating user: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_officers():
    """Fetch all users with the 'officer' role."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.name, u.email, u.phone, u.role_id, r.name as role_name 
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE r.name = 'officer' AND u.deleted_at IS NULL
            """
        )
        rows = cur.fetchall()
        officers = []
        for row in rows:
            officers.append({
                "id": str(row[0]),
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "role_id": row[4],
                "role": row[5]
            })
        return officers
    except Exception as e:
        print(f"Error fetching officers: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_boat_owners():
    """Fetch all users with the 'boat_owner' role."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.name, u.email, u.phone, u.role_id, r.name as role_name 
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE r.name = 'boat_owner' AND u.deleted_at IS NULL
            """
        )
        rows = cur.fetchall()
        boat_owners = []
        for row in rows:
            boat_owners.append({
                "id": str(row[0]),
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "role_id": row[4],
                "role": row[5]
            })
        return boat_owners
    except Exception as e:
        print(f"Error fetching boat owners: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_user_by_id(user_id: str):
    """Fetch a user by their ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.name, u.email, u.phone, u.role_id, r.name as role_name 
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s AND u.deleted_at IS NULL
            """,
            (user_id,)
        )
        row = cur.fetchone()
        if row:
            return {
                "id": str(row[0]),
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "role_id": row[4],
                "role": row[5]
            }
        return None
    except Exception as e:
        print(f"Error fetching user by ID: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def update_user(user_id: str, user_data: dict):
    """Update user details."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Filter out None values and handle specific fields
        update_fields = []
        params = []
        for key, value in user_data.items():
            if value is not None:
                update_fields.append(f"{key} = %s")
                params.append(value)
        
        if not update_fields:
            return True
            
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = %s"
        
        cur.execute(query, tuple(params))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error updating user: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def delete_user(user_id: str):
    """Soft delete a user."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET deleted_at = NOW() WHERE id = %s",
            (user_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error deleting user: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_officer_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """Fetch port officer by phone. Returns None if not found or not officer."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.name, u.email, u.phone
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.phone = %s AND r.name = 'officer' AND u.deleted_at IS NULL
            """,
            (phone.strip(),)
        )
        row = cur.fetchone()
        if row:
            return {"id": str(row[0]), "name": row[1], "email": row[2], "phone": row[3]}
        return None
    except Exception as e:
        print(f"Error fetching officer by phone: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def create_temp_user(name: str, phone: str) -> bool:
    """Store pending boat owner in temp_users (before OTP verify). Replaces existing row for same phone."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM temp_users WHERE phone = %s", (phone.strip(),))
        cur.execute(
            "INSERT INTO temp_users (id, name, phone) VALUES (%s, %s, %s)",
            (str(uuid.uuid4()), name.strip(), phone.strip()),
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error creating temp user: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_temp_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """Fetch temp user (pending registration) by phone. Returns None if not found."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, name, phone FROM temp_users WHERE phone = %s",
            (phone.strip(),),
        )
        row = cur.fetchone()
        if row:
            return {"id": str(row[0]), "name": row[1], "phone": row[2]}
        return None
    except Exception as e:
        print(f"Error fetching temp user by phone: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def delete_temp_user_by_phone(phone: str) -> bool:
    """Remove temp user after successful registration."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM temp_users WHERE phone = %s", (phone.strip(),))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error deleting temp user: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_boat_owner_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """Fetch boat owner by phone. Returns None if not found or not boat_owner role."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.name, u.email, u.phone
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.phone = %s AND r.name = 'boat_owner' AND u.deleted_at IS NULL
            """,
            (phone.strip(),)
        )
        row = cur.fetchone()
        if row:
            return {"id": str(row[0]), "name": row[1], "email": row[2], "phone": row[3]}
        return None
    except Exception as e:
        print(f"Error fetching boat owner by phone: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def _generate_otp(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


def create_and_store_otp(phone: str, expire_minutes: int = 2) -> Tuple[Optional[str], bool]:
    """Create OTP, store in DB, return (otp, success). Invalidates previous OTP for phone."""
    otp = _generate_otp(4)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM password_reset_otps WHERE phone = %s",
            (phone.strip(),)
        )
        cur.execute(
            "INSERT INTO password_reset_otps (phone, otp, expires_at) VALUES (%s, %s, %s)",
            (phone.strip(), otp, expires_at)
        )
        conn.commit()
        return otp, True
    except Exception as e:
        conn.rollback()
        print(f"Error storing OTP: {e}")
        return None, False
    finally:
        cur.close()
        conn.close()


def check_otp(phone: str, otp: str) -> bool:
    """Check if OTP is valid and unused for phone. Does not mark as used (for verify step before reset)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM password_reset_otps
            WHERE phone = %s AND otp = %s AND used_at IS NULL AND expires_at > NOW()
            """,
            (phone.strip(), otp.strip())
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def verify_otp(phone: str, otp: str) -> bool:
    """Verify OTP for phone. Returns True if valid and unused. Marks OTP as used on success."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM password_reset_otps
            WHERE phone = %s AND otp = %s AND used_at IS NULL AND expires_at > NOW()
            """,
            (phone.strip(), otp.strip())
        )
        row = cur.fetchone()
        if not row:
            return False
        cur.execute("UPDATE password_reset_otps SET used_at = NOW() WHERE id = %s", (row[0],))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error verifying OTP: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def mask_mobile(phone: str) -> str:
    """Return masked mobile like XXXX-XX1234."""
    p = phone.replace(" ", "").replace("-", "")
    if len(p) < 4:
        return "XXXX"
    return f"XXXX-XX{p[-4:]}"


# ----- Boat CRUD (boats table) -----
def _boat_from_row(row) -> Dict[str, Any]:
    """Map boats table row to dict. Columns: id, boat_owner_id, boat_number, boat_document, boat_document_content_type, boat_document_filename, created_at, updated_at, deleted_at."""
    boat_document = row[3]
    # Normalize stored paths so they are clickable/openable in clients (Swagger, browser)
    if boat_document and not str(boat_document).startswith(("http://", "https://", "/")):
        boat_document = f"/{boat_document}"
    return {
        "id": str(row[0]),
        "boat_owner_id": str(row[1]),
        "boat_number": row[2],
        "boat_document": boat_document,
        "boat_document_content_type": row[4],
        "boat_document_filename": row[5],
        "created_at": row[6],
        "updated_at": row[7],
    }


def get_boats_by_owner_id(boat_owner_id: str) -> List[Dict[str, Any]]:
    """List boats for one owner (excludes soft-deleted)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, boat_owner_id, boat_number, boat_document, boat_document_content_type, boat_document_filename, created_at, updated_at
            FROM boats WHERE boat_owner_id = %s AND deleted_at IS NULL ORDER BY created_at DESC
            """,
            (boat_owner_id,),
        )
        return [_boat_from_row(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"Error fetching boats by owner: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_all_boats(boat_owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all boats (admin). Optionally filter by boat_owner_id."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if boat_owner_id:
            cur.execute(
                """
                SELECT id, boat_owner_id, boat_number, boat_document, boat_document_content_type, boat_document_filename, created_at, updated_at
                FROM boats WHERE boat_owner_id = %s AND deleted_at IS NULL ORDER BY created_at DESC
                """,
                (boat_owner_id,),
            )
        else:
            cur.execute(
                """
                SELECT id, boat_owner_id, boat_number, boat_document, boat_document_content_type, boat_document_filename, created_at, updated_at
                FROM boats WHERE deleted_at IS NULL ORDER BY created_at DESC
                """
            )
        return [_boat_from_row(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"Error fetching boats: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_boat_by_id(boat_id: str) -> Optional[Dict[str, Any]]:
    """Get one boat by id. Returns None if not found or soft-deleted."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, boat_owner_id, boat_number, boat_document, boat_document_content_type, boat_document_filename, created_at, updated_at
            FROM boats WHERE id = %s AND deleted_at IS NULL
            """,
            (boat_id,),
        )
        row = cur.fetchone()
        return _boat_from_row(row) if row else None
    except Exception as e:
        print(f"Error fetching boat by id: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def create_boat(boat_owner_id: str, data: dict) -> Optional[str]:
    """Create a boat. Returns boat id or None."""
    boat_id = str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO boats (id, boat_owner_id, boat_number, boat_document, boat_document_content_type, boat_document_filename)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                boat_id,
                boat_owner_id,
                data.get("boat_number", "").strip(),
                data.get("boat_document"),
                data.get("boat_document_content_type"),
                data.get("boat_document_filename"),
            ),
        )
        conn.commit()
        return boat_id
    except Exception as e:
        conn.rollback()
        print(f"Error creating boat: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def update_boat(boat_id: str, data: dict) -> bool:
    """Update boat. Only updates provided fields."""
    allowed = {"boat_number", "boat_document", "boat_document_content_type", "boat_document_filename"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        return True
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params = list(updates.values()) + [boat_id]
        cur.execute(f"UPDATE boats SET {set_clause}, updated_at = NOW() WHERE id = %s AND deleted_at IS NULL", tuple(params))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error updating boat: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def delete_boat(boat_id: str) -> bool:
    """Soft delete a boat."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE boats SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL", (boat_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error deleting boat: {e}")
        return False
    finally:
        cur.close()
        conn.close()
