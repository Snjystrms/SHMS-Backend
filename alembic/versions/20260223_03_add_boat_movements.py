"""Add boat_movements table for departure, arrival, partial arrival tracking.

Revision ID: 20260223_03
Revises: 20260223_02
Create Date: 2026-02-23

"""
from alembic import op

revision = "20260223_03"
down_revision = "20260223_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS boat_movements (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            boat_id                 UUID NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
            movement_type           TEXT NOT NULL CHECK (movement_type IN ('departure', 'arrival', 'partial_arrival')),
            movement_at             TIMESTAMPTZ NOT NULL,
            port_name               TEXT,
            crew_count              INTEGER,
            logged_by_user_id       UUID REFERENCES users(id),
            partial_arrival_reason  TEXT,
            partial_arrival_details TEXT,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_boat_movements_boat_id ON boat_movements(boat_id);
        CREATE INDEX idx_boat_movements_boat_movement_at ON boat_movements(boat_id, movement_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS boat_movements;")
