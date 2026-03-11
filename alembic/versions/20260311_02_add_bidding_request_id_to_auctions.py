"""add bidding_request_id to auctions for linking to approved bidding requests

Revision ID: 20260311_02
Revises: 20260311_01
Create Date: 2026-03-11

"""
from alembic import op


revision = "20260311_02"
down_revision = "20260311_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auctions
        ADD COLUMN IF NOT EXISTS bidding_request_id UUID
        REFERENCES bidding_requests(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auctions_bidding_request_id
        ON auctions(bidding_request_id);
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS idx_auctions_bidding_request_id;"
    )
    op.execute(
        "ALTER TABLE auctions DROP COLUMN IF EXISTS bidding_request_id;"
    )
