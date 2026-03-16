"""add registered/unregistered crew counters to users

Revision ID: 20260316_04
Revises: 20260316_03
Create Date: 2026-03-16
"""

from alembic import op


revision = "20260316_04"
down_revision = "20260316_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add separate counter for unregistered crew and recompute both counters
    # using crew_members.is_register.
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS unregistered_crew_count INTEGER NOT NULL DEFAULT 0;
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
                COUNT(*) FILTER (WHERE is_register = TRUE)  AS registered_cnt,
                COUNT(*) FILTER (WHERE is_register = FALSE) AS unregistered_cnt
            FROM crew_members
            WHERE registered_by_user_id IS NOT NULL
            GROUP BY registered_by_user_id
        ) AS sub
        WHERE u.id = sub.user_id;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            DROP COLUMN IF EXISTS unregistered_crew_count;
        """
    )

