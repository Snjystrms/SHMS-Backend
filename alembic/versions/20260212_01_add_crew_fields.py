"""add aadhaar and emergency contact to crew_members

Revision ID: 20260212_01
Revises: 20260209_01
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260212_01"
down_revision = "20260209_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            ADD COLUMN IF NOT EXISTS aadhaar_number TEXT,
            ADD COLUMN IF NOT EXISTS emergency_contact_number TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            DROP COLUMN IF EXISTS emergency_contact_number,
            DROP COLUMN IF EXISTS aadhaar_number;
        """
    )
