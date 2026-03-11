"""add auction_type to auctions for open_box and dutch formats

Revision ID: 20260311_03
Revises: 20260311_02
Create Date: 2026-03-11

"""
from alembic import op


revision = "20260311_03"
down_revision = "20260311_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auctions
        ADD COLUMN IF NOT EXISTS auction_type TEXT NOT NULL
        DEFAULT 'open_box'
        CHECK (auction_type IN ('open_box', 'dutch'));
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE auctions DROP COLUMN IF EXISTS auction_type;"
    )
