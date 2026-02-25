"""add is_register to crew_members (default false for officer-added minimal registrations)

Revision ID: 20260225_01
Revises: 20260224_02
Create Date: 2026-02-25

"""

from alembic import op


revision = "20260225_01"
down_revision = "20260224_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            ADD COLUMN IF NOT EXISTS is_register BOOLEAN NOT NULL DEFAULT false;
        """
    )
    # Existing rows get false; full OTP-verified registrations will be set true by application


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            DROP COLUMN IF EXISTS is_register;
        """
    )
