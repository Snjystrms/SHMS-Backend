"""Add notifications table for admin alerts.

Revision ID: 20260302_03
Revises: 20260302_02
Create Date: 2026-03-02

"""
from alembic import op

revision = "20260302_03"
down_revision = "20260302_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type        TEXT NOT NULL,
            title       TEXT NOT NULL,
            message     TEXT NOT NULL,
            metadata    JSONB,
            recipient_role TEXT NOT NULL DEFAULT 'admin',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            read_at     TIMESTAMPTZ
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications;")
