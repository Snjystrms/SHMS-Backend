"""add default officer and boat owner users

Revision ID: 20260223_01
Revises: 20260220_01
Create Date: 2026-02-23

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260223_01"
down_revision = "20260220_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default officer: login with email officer@example.com or phone 1111111111, password officer123
    officer_id = "00000000-0000-4000-a000-000000000002"
    op.execute(
        f"""
        INSERT INTO users (id, name, email, phone, password, role_id)
        SELECT
            '{officer_id}',
            'Default Officer',
            'officer@example.com',
            '1111111111',
            'officer123',
            id
        FROM roles
        WHERE name = 'officer'
        ON CONFLICT (id) DO NOTHING;
        """
    )

    # Default boat owner: login with phone 2222222222 via OTP (no password)
    boat_owner_id = "00000000-0000-4000-a000-000000000003"
    op.execute(
        f"""
        INSERT INTO users (id, name, email, phone, password, role_id)
        SELECT
            '{boat_owner_id}',
            'Default Boat Owner',
            'boatowner@example.com',
            '2222222222',
            'boatowner123',
            id
        FROM roles
        WHERE name = 'boat_owner'
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'officer@example.com';")
    op.execute("DELETE FROM users WHERE email = 'boatowner@example.com';")
