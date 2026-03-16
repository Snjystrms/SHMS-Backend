"""add registered_by_user_id to crew_members

Revision ID: 20260316_01
Revises: 20260309_03
Create Date: 2026-03-16
"""

from alembic import op


revision = "20260316_01"
down_revision = "20260313_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            ADD COLUMN IF NOT EXISTS registered_by_user_id UUID REFERENCES users(id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE crew_members
            DROP COLUMN IF EXISTS registered_by_user_id;
        """
    )

