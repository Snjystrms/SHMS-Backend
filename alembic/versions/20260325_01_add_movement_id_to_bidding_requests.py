"""Link bidding_requests to arrival movement (one request per agent per arrival).

Revision ID: 20260325_01
Revises: 20260317_02
Create Date: 2026-03-25
"""

from alembic import op


revision = "20260325_01"
down_revision = "20260317_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE bidding_requests
        ADD COLUMN IF NOT EXISTS movement_id UUID
        REFERENCES boat_movements(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bidding_requests_movement_id
        ON bidding_requests(movement_id);
        """
    )
    # Backfill: attach each request to the latest arrival/temporary_arrival at or before created_at.
    op.execute(
        """
        UPDATE bidding_requests br
        SET movement_id = sub.id
        FROM (
            SELECT br2.id AS br_id,
                   (
                       SELECT m.id
                       FROM boat_movements m
                       WHERE m.boat_id = br2.boat_id
                         AND m.movement_type IN ('arrival', 'temporary_arrival')
                         AND m.movement_at <= br2.created_at
                       ORDER BY m.movement_at DESC, m.id DESC
                       LIMIT 1
                   ) AS id
            FROM bidding_requests br2
            WHERE br2.movement_id IS NULL
        ) sub
        WHERE br.id = sub.br_id
          AND sub.id IS NOT NULL;
        """
    )
    # If historical data contains duplicates for the same (agent_id, movement_id),
    # keep the newest and delete the rest so we can enforce the constraint.
    op.execute(
        """
        DELETE FROM bidding_requests br
        USING (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY agent_id, movement_id
                       ORDER BY created_at DESC, id DESC
                   ) AS rn
            FROM bidding_requests
            WHERE movement_id IS NOT NULL
        ) d
        WHERE br.id = d.id
          AND d.rn > 1;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_bidding_requests_agent_movement
        ON bidding_requests(agent_id, movement_id)
        WHERE movement_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_bidding_requests_agent_movement;")
    op.execute("DROP INDEX IF EXISTS idx_bidding_requests_movement_id;")
    op.execute("ALTER TABLE bidding_requests DROP COLUMN IF EXISTS movement_id;")
