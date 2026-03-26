"""Drop GIN index for departure_photo_crew_ids.

We only read departure_photo_crew_ids by movement_id; a GIN index doesn't help that
access pattern and adds write overhead.

Revision ID: 20260326_02_drop_gin_dep_ids
Revises: 20260326_01_dep_photo_ids
Create Date: 2026-03-26
"""

from alembic import op


revision = "20260326_02_drop_gin_dep_ids"
down_revision = "20260326_01_dep_photo_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_boat_movements_departure_photo_crew_ids;")


def downgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_boat_movements_departure_photo_crew_ids
            ON boat_movements USING GIN (departure_photo_crew_ids);
        """
    )

