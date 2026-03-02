"""Add crop_id to boat_movement_crew for crew face image.

Revision ID: 20260302_01
Revises: 20260226_01
Create Date: 2026-03-02

"""
from alembic import op

revision = "20260302_01"
down_revision = "20260226_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE boat_movement_crew
        ADD COLUMN IF NOT EXISTS crop_id TEXT;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE boat_movement_crew
        DROP COLUMN IF EXISTS crop_id;
    """)
