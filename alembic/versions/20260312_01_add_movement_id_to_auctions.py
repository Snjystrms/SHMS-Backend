"""add movement_id to auctions for boat owner self auction

Revision ID: 20260312_01
Revises: 20260311_03
Create Date: 2026-03-12

"""
from alembic import op


revision = "20260312_01"
down_revision = "20260311_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auctions
        ADD COLUMN IF NOT EXISTS movement_id UUID
        REFERENCES boat_movements(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auctions_movement_id
        ON auctions(movement_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_auctions_movement_id;")
    op.execute("ALTER TABLE auctions DROP COLUMN IF EXISTS movement_id;")
