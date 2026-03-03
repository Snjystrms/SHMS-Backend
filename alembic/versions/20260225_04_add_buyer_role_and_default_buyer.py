"""add buyer role and default buyer user

Revision ID: 20260225_04
Revises: 20260225_03_img
Create Date: 2026-02-25
"""

from alembic import op


revision = "20260225_04"
down_revision = "20260225_03_img"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add buyer role if it doesn't exist
    op.execute(
        """
        INSERT INTO roles (name)
        VALUES ('buyer')
        ON CONFLICT (name) DO NOTHING;
        """
    )

    # Default buyer user: simple demo account
    buyer_id = "00000000-0000-4000-a000-000000000004"
    op.execute(
        f"""
        INSERT INTO users (id, name, email, phone, password, role_id)
        SELECT
            '{buyer_id}',
            'Default Buyer',
            'buyer@example.com',
            '3333333333',
            'buyer123',
            id
        FROM roles
        WHERE name = 'buyer'
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'buyer@example.com';")
    op.execute("DELETE FROM roles WHERE name = 'buyer';")

