"""add is_pilot to crew_members

Revision ID: 20260224_01
Revises: 20260223_03
Create Date: 2026-02-24

"""

from alembic import op


revision = "20260224_01"
down_revision = "20260223_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            ADD COLUMN IF NOT EXISTS is_pilot BOOLEAN NOT NULL DEFAULT false;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            DROP COLUMN IF EXISTS is_pilot;
        """
    )
