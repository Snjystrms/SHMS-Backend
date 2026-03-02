"""Add priority column to notifications.

Revision ID: 20260302_04
Revises: 20260302_03
Create Date: 2026-03-02

"""
from alembic import op

revision = "20260302_04"
down_revision = "20260302_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE notifications
        ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'normal';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE notifications DROP COLUMN IF EXISTS priority;
        """
    )
