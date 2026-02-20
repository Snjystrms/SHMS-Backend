"""Add boat_name, boat_type, harbor_name columns to boats table.

Revision ID: 20260220_01
Revises: 20260217_03_add_boats
Create Date: 2026-02-20
"""
from alembic import op

revision = "20260220_01"
down_revision = "20260217_03"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE boats
        ADD COLUMN IF NOT EXISTS boat_name TEXT,
        ADD COLUMN IF NOT EXISTS boat_type TEXT,
        ADD COLUMN IF NOT EXISTS harbor_name TEXT DEFAULT 'mumbai';
    """)


def downgrade():
    op.execute("""
        ALTER TABLE boats
        DROP COLUMN IF EXISTS boat_name,
        DROP COLUMN IF EXISTS boat_type,
        DROP COLUMN IF EXISTS harbor_name;
    """)
