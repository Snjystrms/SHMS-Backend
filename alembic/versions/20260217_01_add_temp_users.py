"""add temp_users table for boat owner registration before OTP verify

Revision ID: 20260217_01
Revises: 20260216_02
Create Date: 2026-02-17

"""
from alembic import op


revision = "20260217_01"
down_revision = "20260216_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS temp_users (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name       TEXT NOT NULL,
            phone      TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_temp_users_phone ON temp_users(phone);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS temp_users;")
