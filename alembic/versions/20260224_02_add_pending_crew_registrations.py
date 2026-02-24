"""add pending_crew_registrations table for OTP verification before crew creation

Revision ID: 20260224_02
Revises: 20260224_01
Create Date: 2026-02-24

"""

from alembic import op


revision = "20260224_02"
down_revision = "20260224_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_crew_registrations (
            id                      UUID PRIMARY KEY,
            phone                   TEXT NOT NULL,
            name                    TEXT NOT NULL,
            aadhaar_number          TEXT,
            emergency_contact_number TEXT,
            is_pilot                BOOLEAN NOT NULL DEFAULT false,
            embedding               VECTOR(512) NOT NULL,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_crew_phone ON pending_crew_registrations(phone);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pending_crew_phone;")
    op.execute("DROP TABLE IF EXISTS pending_crew_registrations;")

