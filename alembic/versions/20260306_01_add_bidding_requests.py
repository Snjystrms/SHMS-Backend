"""Add bidding_requests table for agent-to-boat-owner bidding flow.

Revision ID: 20260306_01
Revises: 20260303_01
Create Date: 2026-03-06
"""

from alembic import op

revision = "20260306_01"
down_revision = "20260303_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS bidding_requests (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            boat_id         UUID NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
            agent_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            boat_owner_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected')),
            note            TEXT,
            responded_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_bidding_requests_boat_id ON bidding_requests(boat_id);
        CREATE INDEX idx_bidding_requests_agent_id ON bidding_requests(agent_id);
        CREATE INDEX idx_bidding_requests_boat_owner_id ON bidding_requests(boat_owner_id);
        CREATE INDEX idx_bidding_requests_status ON bidding_requests(status);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bidding_requests;")
