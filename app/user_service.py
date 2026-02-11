from app.database import conn
from typing import Optional
import uuid

def get_user_by_email(email: str):
    """Fetch a user by their email address."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.name, u.email, u.password, u.role_id, r.name as role_name 
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.email = %s AND u.deleted_at IS NULL
            """,
            (email,)
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
        print(f"Error fetching user by email: {e}")
        return None
    finally:
        cur.close()

def update_user_password(user_id: str, hashed_password: str):
    """Update a user's password with a new hash."""
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
    finally:
        cur.close()


def get_role_id_by_name(role_name: str):
    """Fetch role ID by role name."""
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


def create_user(user_data: dict, role_id: int):
    """Create a new user in the database."""
    user_id = str(uuid.uuid4())
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
