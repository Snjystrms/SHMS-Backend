"""add delivered_quantity to auctions table

Revision ID: 20260312_03
Revises: 20260312_02
Create Date: 2026-03-12

"""
from alembic import op


revision = "20260312_03"
down_revision = "20260312_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auctions
        ADD COLUMN IF NOT EXISTS delivered_quantity NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (delivered_quantity >= 0);
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE auctions DROP COLUMN IF EXISTS delivered_quantity;")
