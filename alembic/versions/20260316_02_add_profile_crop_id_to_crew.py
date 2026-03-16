"""add profile_crop_id to crew tables

Revision ID: 20260316_02
Revises: 20260316_01
Create Date: 2026-03-16
"""

from alembic import op


revision = "20260316_02"
down_revision = "20260316_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            ADD COLUMN IF NOT EXISTS profile_crop_id UUID;
        """
    )
    op.execute(
        """
        ALTER TABLE pending_crew_registrations
            ADD COLUMN IF NOT EXISTS profile_crop_id UUID;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE pending_crew_registrations
            DROP COLUMN IF EXISTS profile_crop_id;
        """
    )
    op.execute(
        """
        ALTER TABLE crew_members
            DROP COLUMN IF EXISTS profile_crop_id;
        """
    )

