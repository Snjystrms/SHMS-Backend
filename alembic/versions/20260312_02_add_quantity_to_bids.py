"""add quantity to bids table

Revision ID: 20260312_02
Revises: 20260312_01
Create Date: 2026-03-12

"""
from alembic import op


revision = "20260312_02"
down_revision = "20260312_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE bids
        ADD COLUMN IF NOT EXISTS quantity NUMERIC(12, 2) NOT NULL DEFAULT 1
        CHECK (quantity > 0);
        """
    )
    op.execute(
        """
        ALTER TABLE bids
        ALTER COLUMN quantity DROP DEFAULT;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE bids DROP COLUMN IF EXISTS quantity;")
