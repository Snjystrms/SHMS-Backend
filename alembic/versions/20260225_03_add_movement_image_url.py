"""Add image_url to boat_movements for departure/arrival/partial_arrival images.

Revision ID: 20260225_03_img
Revises: 20260225_02
Create Date: 2026-02-25

"""
from alembic import op

revision = "20260225_03_img"
down_revision = "20260225_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE boat_movements
        ADD COLUMN IF NOT EXISTS image_url TEXT;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE boat_movements
        DROP COLUMN IF EXISTS image_url;
    """)
