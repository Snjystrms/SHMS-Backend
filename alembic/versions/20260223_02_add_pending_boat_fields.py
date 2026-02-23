"""Add is_register and owner_mobile for pending boat registration.

Revision ID: 20260223_02
Revises: 20260223_01
Create Date: 2026-02-23

"""
from alembic import op

revision = "20260223_02"
down_revision = "20260223_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE boats
        ADD COLUMN IF NOT EXISTS is_register BOOLEAN NOT NULL DEFAULT true,
        ADD COLUMN IF NOT EXISTS owner_mobile TEXT;
    """)
    op.execute("ALTER TABLE boats ALTER COLUMN boat_owner_id DROP NOT NULL;")


def downgrade() -> None:
    op.execute("DELETE FROM boats WHERE boat_owner_id IS NULL;")
    op.execute("ALTER TABLE boats ALTER COLUMN boat_owner_id SET NOT NULL;")
    op.execute("""
        ALTER TABLE boats
        DROP COLUMN IF EXISTS is_register,
        DROP COLUMN IF EXISTS owner_mobile;
    """)
