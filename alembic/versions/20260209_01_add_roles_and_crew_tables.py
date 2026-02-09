"""add roles and crew tables

Revision ID: 20260209_01
Revises: 
Create Date: 2026-02-09
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260209_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # roles table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id          SERIAL PRIMARY KEY,
            name        TEXT UNIQUE NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at  TIMESTAMPTZ
        );
        """
    )

    op.execute(
        """
        INSERT INTO roles (name) VALUES
            ('admin'),
            ('boat_owner'),
            ('officer')
        ON CONFLICT (name) DO NOTHING;
        """
    )

    # users table (initial creation if missing)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id          UUID PRIMARY KEY,
            name        TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    # users table extensions
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS email       TEXT,
            ADD COLUMN IF NOT EXISTS phone       TEXT,
            ADD COLUMN IF NOT EXISTS password    TEXT,
            ADD COLUMN IF NOT EXISTS role_id     INTEGER REFERENCES roles(id),
            ADD COLUMN IF NOT EXISTS created_at  TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS updated_at  TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS deleted_at  TIMESTAMPTZ;
        """
    )

    # crew_members table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS crew_members (
            id          UUID PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT,
            phone       TEXT,
            role_id     INTEGER REFERENCES roles(id),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at  TIMESTAMPTZ
        );
        """
    )

    # crew_face_embeddings table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS crew_face_embeddings (
            id             UUID PRIMARY KEY,
            crew_member_id UUID NOT NULL REFERENCES crew_members(id) ON DELETE CASCADE,
            embedding      VECTOR(512) NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.execute("DROP TABLE IF EXISTS crew_face_embeddings;")
    op.execute("DROP TABLE IF EXISTS crew_members;")

    # remove columns from users (safe even if some not present)
    op.execute(
        """
        ALTER TABLE users
            DROP COLUMN IF EXISTS deleted_at,
            DROP COLUMN IF EXISTS updated_at,
            DROP COLUMN IF EXISTS created_at,
            DROP COLUMN IF EXISTS role_id,
            DROP COLUMN IF EXISTS password,
            DROP COLUMN IF EXISTS phone,
            DROP COLUMN IF EXISTS email;
        """
    )

    op.execute("DROP TABLE IF EXISTS roles;")

