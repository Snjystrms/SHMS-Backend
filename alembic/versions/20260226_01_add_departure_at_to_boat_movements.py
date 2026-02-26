"""Add departure_at to boat_movements so arrival updates the same row and keeps departure time.

Revision ID: 20260226_01
Revises: 20260225_03_img
Create Date: 2026-02-26

"""
from alembic import op

revision = "20260226_01"
down_revision = "20260225_03_img"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE boat_movements
        ADD COLUMN IF NOT EXISTS departure_at TIMESTAMPTZ;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE boat_movements
        DROP COLUMN IF EXISTS departure_at;
    """)
