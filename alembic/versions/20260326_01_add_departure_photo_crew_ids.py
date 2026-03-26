"""Add departure_photo_crew_ids to boat_movements.

Stores the crew ids detected in the departure group photo so arrival crew scan
can compare against the departure photo without re-running face identification.

Revision ID: 20260326_01_dep_photo_ids
Revises: 20260325_01
Create Date: 2026-03-26
"""

from alembic import op


revision = "20260326_01_dep_photo_ids"
down_revision = "20260325_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE boat_movements
        ADD COLUMN IF NOT EXISTS departure_photo_crew_ids JSONB;
        CREATE INDEX IF NOT EXISTS idx_boat_movements_departure_photo_crew_ids
            ON boat_movements USING GIN (departure_photo_crew_ids);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_boat_movements_departure_photo_crew_ids;
        ALTER TABLE boat_movements
        DROP COLUMN IF EXISTS departure_photo_crew_ids;
        """
    )

