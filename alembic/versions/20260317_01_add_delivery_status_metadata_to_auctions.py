"""add delivery status + metadata columns to auctions

Revision ID: 20260317_01
Revises: 20260316_05
Create Date: 2026-03-17

"""

from alembic import op


revision = "20260317_01"
down_revision = "20260316_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auctions
            ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS delivery_recorded_by UUID NULL REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS delivery_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (delivery_status IN ('pending', 'completed'));
        """
    )

    # Backfill delivery_status for already completed auctions with winners.
    # requested_quantity is taken from the winner's highest bid (max amount).
    op.execute(
        """
        WITH winner_bids AS (
            SELECT DISTINCT ON (b.auction_id)
                b.auction_id,
                b.quantity AS requested_quantity
            FROM bids b
            JOIN auctions a
              ON a.id = b.auction_id
             AND a.winner_id = b.bidder_id
            WHERE a.status = 'completed'
              AND a.winner_id IS NOT NULL
            ORDER BY b.auction_id, b.amount DESC, b.created_at ASC
        )
        UPDATE auctions a
        SET delivery_status = CASE
                WHEN wb.requested_quantity IS NOT NULL
                 AND wb.requested_quantity > 0
                 AND a.delivered_quantity >= wb.requested_quantity
                THEN 'completed'
                ELSE 'pending'
            END
        FROM winner_bids wb
        WHERE a.id = wb.auction_id
          AND a.status = 'completed'
          AND a.winner_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE auctions DROP COLUMN IF EXISTS delivery_status;")
    op.execute("ALTER TABLE auctions DROP COLUMN IF EXISTS delivery_recorded_by;")
    op.execute("ALTER TABLE auctions DROP COLUMN IF EXISTS delivered_at;")

