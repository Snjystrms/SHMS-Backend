"""add agent and buyer roles

Revision ID: 20260303_01
Revises: 20260302_04
Create Date: 2026-03-03
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260303_01"
down_revision = "20260302_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Insert new roles if they don't already exist
    op.execute(
        """
        INSERT INTO roles (name)
        VALUES
            ('agent'),
            ('buyer')
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Remove the roles that were added in this migration
    op.execute(
        """
        DELETE FROM roles
        WHERE name IN ('agent', 'buyer');
        """
    )

