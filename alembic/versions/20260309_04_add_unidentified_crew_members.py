"""add unidentified_crew_members table

Revision ID: 20260309_04
Revises: 20260309_03
Create Date: 2026-03-09
"""

from alembic import op

revision = "20260309_04"
down_revision = "20260309_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS unidentified_crew_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            movement_id UUID NOT NULL REFERENCES boat_movements(id) ON DELETE CASCADE,
            crop_image_url TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS unidentified_crew_members;")
