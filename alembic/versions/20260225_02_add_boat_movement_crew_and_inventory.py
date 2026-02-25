"""Add tables for boat movement crew and inventory.

Revision ID: 20260225_02
Revises: 20260225_01
Create Date: 2026-02-25

"""
from alembic import op


revision = "20260225_02"
down_revision = "20260225_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS boat_movement_crew (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            movement_id    UUID NOT NULL REFERENCES boat_movements(id) ON DELETE CASCADE,
            crew_member_id UUID NOT NULL REFERENCES crew_members(id) ON DELETE CASCADE,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_boat_movement_crew_movement_id
            ON boat_movement_crew(movement_id);

        CREATE TABLE IF NOT EXISTS boat_movement_inventory (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            movement_id          UUID NOT NULL REFERENCES boat_movements(id) ON DELETE CASCADE,
            diesel_liters        DOUBLE PRECISION,
            ice_blocks           INTEGER,
            fishing_net_count    INTEGER,
            plastic_bottle_count INTEGER,
            plastic_bag_count    INTEGER,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_boat_movement_inventory_movement_id
            ON boat_movement_inventory(movement_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS boat_movement_inventory;
        DROP TABLE IF EXISTS boat_movement_crew;
        """
    )

