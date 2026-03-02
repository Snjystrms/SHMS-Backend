"""Add aadhaar_number and emergency_contact_number to users for officers.

Revision ID: 20260302_02
Revises: 20260302_01
Create Date: 2026-03-02

"""
from alembic import op

revision = "20260302_02"
down_revision = "20260302_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS aadhaar_number TEXT,
            ADD COLUMN IF NOT EXISTS emergency_contact_number TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            DROP COLUMN IF EXISTS emergency_contact_number,
            DROP COLUMN IF EXISTS aadhaar_number;
        """
    )
