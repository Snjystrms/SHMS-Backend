"""add user_id to password_reset_otps

Revision ID: 20260216_02
Revises: 20260216_01
Create Date: 2026-02-16

"""
from alembic import op


revision = "20260216_02"
down_revision = "20260216_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE password_reset_otps
        ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
        CREATE INDEX IF NOT EXISTS idx_password_reset_otps_user_id ON password_reset_otps(user_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_password_reset_otps_user_id;
        ALTER TABLE password_reset_otps DROP COLUMN IF EXISTS user_id;
        """
    )
