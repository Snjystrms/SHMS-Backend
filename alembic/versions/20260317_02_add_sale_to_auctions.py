"""add sale column to auctions

Revision ID: 20260317_02
Revises: 20260317_01
Create Date: 2026-03-17

"""

from alembic import op


revision = "20260317_02"
down_revision = "20260317_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auctions
            ADD COLUMN IF NOT EXISTS sale DOUBLE PRECISION NULL;
        """
    )

    # Backfill sale for auctions that already have delivery recorded.
    # sale = winning bid amount * winning bid quantity
    op.execute(
        """
        WITH winner_bids AS (
            SELECT DISTINCT ON (b.auction_id)
                b.auction_id,
                b.amount AS winning_amount,
                b.quantity AS winning_quantity
            FROM bids b
            JOIN auctions a
              ON a.id = b.auction_id
             AND a.winner_id = b.bidder_id
            WHERE a.winner_id IS NOT NULL
            ORDER BY b.auction_id, b.amount DESC, b.created_at ASC
        )
        UPDATE auctions a
        SET sale = (wb.winning_amount * wb.winning_quantity)
        FROM winner_bids wb
        WHERE a.id = wb.auction_id
          AND (a.delivered_at IS NOT NULL OR COALESCE(a.delivered_quantity, 0) > 0)
          AND a.sale IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE auctions DROP COLUMN IF EXISTS sale;")

