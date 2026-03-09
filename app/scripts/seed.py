"""
Seed default admin, officer, and boat owner users. Safe to run multiple times (uses ON CONFLICT DO NOTHING).

Run after migrations:
  python -m app.scripts.seed
"""
from app.db.session import get_db_connection
from app.core.security import get_password_hash

DEFAULT_ADMIN_ID = "00000000-0000-4000-a000-000000000001"
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "admin123"

DEFAULT_OFFICER_ID = "00000000-0000-4000-a000-000000000002"
DEFAULT_OFFICER_EMAIL = "officer@example.com"
DEFAULT_OFFICER_PHONE = "1111111111"
DEFAULT_OFFICER_PASSWORD = "officer123"

DEFAULT_BOAT_OWNER_ID = "00000000-0000-4000-a000-000000000003"
DEFAULT_BOAT_OWNER_EMAIL = "boatowner@example.com"
DEFAULT_BOAT_OWNER_PHONE = "2222222222"

# Two demo buyers for testing the marketplace/auction flows.
DEFAULT_BUYER1_ID = "00000000-0000-4000-a000-000000000005"
DEFAULT_BUYER1_EMAIL = "buyer1@example.com"
DEFAULT_BUYER1_PHONE = "3333333333"
DEFAULT_BUYER1_PASSWORD = "buyer123"

DEFAULT_BUYER2_ID = "00000000-0000-4000-a000-000000000006"
DEFAULT_BUYER2_EMAIL = "buyer2@example.com"
DEFAULT_BUYER2_PHONE = "4444444444"
DEFAULT_BUYER2_PASSWORD = "buyer123"


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


def seed_default_officer() -> bool:
    """Insert default officer if missing. Returns True if inserted, False if already existed."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM roles WHERE name = 'officer' LIMIT 1;")
            row = cur.fetchone()
            if not row:
                print("No 'officer' role found. Run migrations first: alembic upgrade head")
                return False
            role_id = row[0]
            hashed = get_password_hash(DEFAULT_OFFICER_PASSWORD)
            cur.execute(
                """
                INSERT INTO users (id, name, email, phone, password, role_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (
                    DEFAULT_OFFICER_ID,
                    "Default Officer",
                    DEFAULT_OFFICER_EMAIL,
                    DEFAULT_OFFICER_PHONE,
                    hashed,
                    role_id,
                ),
            )
            conn.commit()
            inserted = cur.rowcount > 0
            if inserted:
                print(f"Default officer created: {DEFAULT_OFFICER_EMAIL} / {DEFAULT_OFFICER_PASSWORD}")
            else:
                print(f"Default officer already exists: {DEFAULT_OFFICER_EMAIL}")
            return inserted
    finally:
        conn.close()


def seed_default_boat_owner() -> bool:
    """Insert default boat owner if missing. Returns True if inserted, False if already existed."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM roles WHERE name = 'boat_owner' LIMIT 1;")
            row = cur.fetchone()
            if not row:
                print("No 'boat_owner' role found. Run migrations first: alembic upgrade head")
                return False
            role_id = row[0]
            cur.execute(
                """
                INSERT INTO users (id, name, email, phone, password, role_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (
                    DEFAULT_BOAT_OWNER_ID,
                    "Default Boat Owner",
                    DEFAULT_BOAT_OWNER_EMAIL,
                    DEFAULT_BOAT_OWNER_PHONE,
                    None,  # Boat owners use OTP login, no password
                    role_id,
                ),
            )
            conn.commit()
            inserted = cur.rowcount > 0
            if inserted:
                print(f"Default boat owner created: {DEFAULT_BOAT_OWNER_PHONE} (login via OTP)")
            else:
                print(f"Default boat owner already exists: {DEFAULT_BOAT_OWNER_PHONE}")
            return inserted
    finally:
        conn.close()


def seed_default_buyers() -> None:
    """
    Insert two default buyer users if missing.

    Safe to run multiple times thanks to ON CONFLICT (id) DO NOTHING.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get buyer role_id
            cur.execute("SELECT id FROM roles WHERE name = 'buyer' LIMIT 1;")
            row = cur.fetchone()
            if not row:
                print("No 'buyer' role found. Run migrations first: alembic upgrade head")
                return
            role_id = row[0]

            # Buyer 1
            hashed1 = get_password_hash(DEFAULT_BUYER1_PASSWORD)
            cur.execute(
                """
                INSERT INTO users (id, name, email, phone, password, role_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (
                    DEFAULT_BUYER1_ID,
                    "Default Buyer 1",
                    DEFAULT_BUYER1_EMAIL,
                    DEFAULT_BUYER1_PHONE,
                    hashed1,
                    role_id,
                ),
            )

            # Buyer 2
            hashed2 = get_password_hash(DEFAULT_BUYER2_PASSWORD)
            cur.execute(
                """
                INSERT INTO users (id, name, email, phone, password, role_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (
                    DEFAULT_BUYER2_ID,
                    "Default Buyer 2",
                    DEFAULT_BUYER2_EMAIL,
                    DEFAULT_BUYER2_PHONE,
                    hashed2,
                    role_id,
                ),
            )

            conn.commit()

            print(
                f"Default buyers ensured:\n"
                f"  - {DEFAULT_BUYER1_EMAIL} / {DEFAULT_BUYER1_PASSWORD}\n"
                f"  - {DEFAULT_BUYER2_EMAIL} / {DEFAULT_BUYER2_PASSWORD}"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    seed_default_admin()
    seed_default_officer()
    seed_default_boat_owner()
    seed_default_buyers()