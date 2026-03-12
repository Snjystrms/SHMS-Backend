"""add dashboard performance indexes

Revision ID: 20260312_04
Revises: 20260312_03
Create Date: 2026-03-12

"""
from alembic import op


revision = "20260312_04"
down_revision = "20260312_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        -- Boat movement filters used by dashboard counts and arrival lists
        CREATE INDEX IF NOT EXISTS idx_boat_movements_type_movement_at
            ON boat_movements(movement_type, movement_at DESC);

        -- Latest movement + type filtering per boat (owner and status computations)
        CREATE INDEX IF NOT EXISTS idx_boat_movements_boat_type_movement_at
            ON boat_movements(boat_id, movement_type, movement_at DESC);

        -- Fast bidder->auction max(amount) lookup for buyer live auctions
        CREATE INDEX IF NOT EXISTS idx_bids_bidder_auction_amount
            ON bids(bidder_id, auction_id, amount DESC);

        -- Agent's latest request per boat (DISTINCT ON boat_id ORDER BY created_at DESC)
        CREATE INDEX IF NOT EXISTS idx_bidding_requests_agent_boat_created_at
            ON bidding_requests(agent_id, boat_id, created_at DESC);

        -- Pending request counts by boat on owner dashboard
        CREATE INDEX IF NOT EXISTS idx_bidding_requests_boat_status
            ON bidding_requests(boat_id, status);

        -- Active auctions ordered by start_time on buyer dashboard
        CREATE INDEX IF NOT EXISTS idx_auctions_status_start_time
            ON auctions(status, start_time);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_auctions_status_start_time;")
    op.execute("DROP INDEX IF EXISTS idx_bidding_requests_boat_status;")
    op.execute("DROP INDEX IF EXISTS idx_bidding_requests_agent_boat_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_bids_bidder_auction_amount;")
    op.execute("DROP INDEX IF EXISTS idx_boat_movements_boat_type_movement_at;")
    op.execute("DROP INDEX IF EXISTS idx_boat_movements_type_movement_at;")
