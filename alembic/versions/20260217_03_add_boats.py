"""add boats table (boat number, boat_document path/type) for boat owners

Revision ID: 20260217_03
Revises: 20260217_02
Create Date: 2026-02-17

"""
from alembic import op


revision = "20260217_03"
down_revision = "20260217_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS boats (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            boat_owner_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            boat_number                 TEXT NOT NULL,
            boat_document               TEXT,
            boat_document_content_type  TEXT,
            boat_document_filename      TEXT,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at                 TIMESTAMPTZ,
            UNIQUE(boat_owner_id, boat_number)
        );
        CREATE INDEX IF NOT EXISTS idx_boats_boat_owner_id ON boats(boat_owner_id);
        CREATE INDEX IF NOT EXISTS idx_boats_boat_number ON boats(boat_number);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS boats;")
