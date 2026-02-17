"""
Seed default admin user. Safe to run multiple times (uses ON CONFLICT DO NOTHING).

Run after migrations:
  python -m app.scripts.seed
"""
from app.db.session import get_db_connection
from app.core.security import get_password_hash

DEFAULT_ADMIN_ID = "00000000-0000-4000-a000-000000000001"
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "admin123"


def seed_default_admin() -> bool:
    """Insert default admin if missing. Returns True if inserted, False if already existed."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM roles WHERE name = 'admin' LIMIT 1;")
            row = cur.fetchone()
            if not row:
                print("No 'admin' role found. Run migrations first: alembic upgrade head")
                return False
            role_id = row[0]
            hashed = get_password_hash(DEFAULT_ADMIN_PASSWORD)
            cur.execute(
                """
                INSERT INTO users (id, name, email, phone, password, role_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (
                    DEFAULT_ADMIN_ID,
                    "Default Admin",
                    DEFAULT_ADMIN_EMAIL,
                    "0000000000",
                    hashed,
                    role_id,
                ),
            )
            conn.commit()
            inserted = cur.rowcount > 0
            if inserted:
                print(f"Default admin created: {DEFAULT_ADMIN_EMAIL} / {DEFAULT_ADMIN_PASSWORD}")
            else:
                print(f"Default admin already exists: {DEFAULT_ADMIN_EMAIL}")
            return inserted
    finally:
        conn.close()


if __name__ == "__main__":
    seed_default_admin()
