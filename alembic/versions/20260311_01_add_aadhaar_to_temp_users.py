"""add aadhaar_number to temp_users for buyer registration

Revision ID: 20260311_01
Revises: 20260309_04
Create Date: 2026-03-11

"""
from alembic import op


revision = "20260311_01"
down_revision = "5da154916a6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE temp_users ADD COLUMN IF NOT EXISTS aadhaar_number TEXT;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE temp_users DROP COLUMN IF EXISTS aadhaar_number;"
    )
