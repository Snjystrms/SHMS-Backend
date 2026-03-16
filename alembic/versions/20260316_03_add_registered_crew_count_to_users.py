"""add registered_crew_count to users

Revision ID: 20260316_03
Revises: 20260316_02
Create Date: 2026-03-16
"""

from alembic import op


revision = "20260316_03"
down_revision = "20260316_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add denormalized counter column on users for how many crew members
    # were registered by that user (officer).
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS registered_crew_count INTEGER NOT NULL DEFAULT 0;
        """
    )

    # Backfill counts from existing crew_members.registered_by_user_id data.
    op.execute(
        """
        UPDATE users u
        SET registered_crew_count = sub.cnt
        FROM (
            SELECT registered_by_user_id AS user_id, COUNT(*) AS cnt
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
            DROP COLUMN IF EXISTS registered_crew_count;
        """
    )

