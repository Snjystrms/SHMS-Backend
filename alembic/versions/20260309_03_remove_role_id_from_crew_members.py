"""remove role_id from crew_members table

Revision ID: 20260309_03
Revises: 20260309_02
Create Date: 2026-03-09
"""

from alembic import op

revision = "20260309_03"
down_revision = "20260309_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE crew_members DROP COLUMN IF EXISTS role_id;")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE crew_members ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(id);"
    )
