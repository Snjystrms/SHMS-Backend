"""add auctions and bids tables for fish auctions

Revision ID: 20260224_03_auction
Revises: 20260224_02
Create Date: 2026-02-24

"""

from alembic import op


revision = "20260224_03_auction"
down_revision = "20260224_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        -- Auctions table: fish auctions created by boat owners / sellers
        CREATE TABLE IF NOT EXISTS auctions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            seller_id       UUID NOT NULL REFERENCES users(id),
            fish_name       TEXT NOT NULL,
            initial_price   NUMERIC(12, 2) NOT NULL CHECK (initial_price > 0),
            current_price   NUMERIC(12, 2) NOT NULL CHECK (current_price >= 0),
            start_time      TIMESTAMPTZ NOT NULL,
            end_time        TIMESTAMPTZ NOT NULL,
            status          TEXT NOT NULL CHECK (status IN ('scheduled', 'active', 'completed', 'cancelled')),
            winner_id       UUID REFERENCES users(id),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_auctions_time_status
            ON auctions (start_time, end_time, status);

        -- Bids table: bids placed on auctions
        CREATE TABLE IF NOT EXISTS bids (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            auction_id  UUID NOT NULL REFERENCES auctions(id) ON DELETE CASCADE,
            bidder_id   UUID NOT NULL REFERENCES users(id),
            amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_bids_auction_created_at
            ON bids (auction_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_bids_bidder_created_at
            ON bids (bidder_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS bids;
        DROP TABLE IF EXISTS auctions;
        """
    )

