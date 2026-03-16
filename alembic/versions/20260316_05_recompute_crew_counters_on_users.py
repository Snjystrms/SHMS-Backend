"""recompute crew registration counters on users

Revision ID: 20260316_05
Revises: 20260316_04
Create Date: 2026-03-16
"""

from alembic import op


revision = "20260316_05"
down_revision = "20260316_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure columns exist (idempotent) and recompute counters from crew_members.
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS registered_crew_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS unregistered_crew_count INTEGER NOT NULL DEFAULT 0;
        """
    )

    op.execute(
        """
        UPDATE users
        SET registered_crew_count = 0,
            unregistered_crew_count = 0;
        """
    )

    op.execute(
        """
        UPDATE users u
        SET
            registered_crew_count = COALESCE(sub.registered_cnt, 0),
            unregistered_crew_count = COALESCE(sub.unregistered_cnt, 0)
        FROM (
            SELECT
                registered_by_user_id AS user_id,
                COUNT(*) FILTER (WHERE is_register = TRUE  AND deleted_at IS NULL) AS registered_cnt,
                COUNT(*) FILTER (WHERE is_register = FALSE AND deleted_at IS NULL) AS unregistered_cnt
            FROM crew_members
            WHERE registered_by_user_id IS NOT NULL
            GROUP BY registered_by_user_id
        ) AS sub
        WHERE u.id = sub.user_id;
        """
    )


def downgrade() -> None:
    # Pure recompute migration; no schema change to revert.
    pass

