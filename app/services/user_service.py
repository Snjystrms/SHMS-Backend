import uuid
from typing import Optional, List, Dict, Any
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
            INSERT INTO users (id, name, email, phone, password, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                user_id,
                user_data["name"],
                user_data["email"],
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
