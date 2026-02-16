"""add password_reset_otps table

Revision ID: 20260216_01
Revises: 20260212_01
Create Date: 2026-02-16

"""
from alembic import op


revision = "20260216_01"
down_revision = "20260212_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phone       TEXT NOT NULL,
            otp         TEXT NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_password_reset_otps_phone ON password_reset_otps(phone);
        CREATE INDEX IF NOT EXISTS idx_password_reset_otps_expires ON password_reset_otps(expires_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_otps;")
