"""Add temporary_departure and temporary_arrival to movement_type CHECK constraint.

Revision ID: 20260313_01
Revises: 20260312_04
Create Date: 2026-03-13

"""
from alembic import op


revision = "20260313_01"
down_revision = "20260312_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE boat_movements DROP CONSTRAINT IF EXISTS boat_movements_movement_type_check;
        ALTER TABLE boat_movements ADD CONSTRAINT boat_movements_movement_type_check
            CHECK (movement_type IN ('departure', 'arrival', 'partial_arrival', 'temporary_departure', 'temporary_arrival'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE boat_movements DROP CONSTRAINT IF EXISTS boat_movements_movement_type_check;
        ALTER TABLE boat_movements ADD CONSTRAINT boat_movements_movement_type_check
            CHECK (movement_type IN ('departure', 'arrival', 'partial_arrival'));
        """
    )
