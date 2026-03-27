"""Add indexes for crew face embedding lookup performance.

Revision ID: 20260327_01_face_emb_idx
Revises: 20260326_02_drop_gin_dep_ids
Create Date: 2026-03-27
"""

from alembic import op


revision = "20260327_01_face_emb_idx"
down_revision = "20260326_02_drop_gin_dep_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Speed up nearest-neighbor cosine search used by find_match().
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cfe_embedding_ivfflat_cosine
            ON crew_face_embeddings
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """
    )
    # Speed up joins and any crew-member scoped embedding lookups.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cfe_crew_member_id
            ON crew_face_embeddings (crew_member_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cfe_crew_member_id;")
    op.execute("DROP INDEX IF EXISTS idx_cfe_embedding_ivfflat_cosine;")

