"""add created_at to users table if not exists

Revision ID: 20260217_02
Revises: 20260217_01
Create Date: 2026-02-17

"""
from alembic import op


revision = "20260217_02"
down_revision = "20260217_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users DROP COLUMN IF EXISTS created_at;
        """
    )
