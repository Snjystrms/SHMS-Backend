"""add default agent and buyer users

Revision ID: 20260309_01
Revises: 20260306_01
Create Date: 2026-03-09
"""

from alembic import op

revision = "20260309_01"
down_revision = "20260306_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    agent_id = "00000000-0000-4000-a000-000000000004"
    op.execute(
        f"""
        INSERT INTO users (id, name, email, phone, password, role_id)
        SELECT
            '{agent_id}',
            'Default Agent',
            'agent@example.com',
            '3333333333',
            'agent123',
            id
        FROM roles
        WHERE name = 'agent'
        ON CONFLICT (id) DO NOTHING;
        """
    )

    buyer_id = "00000000-0000-4000-a000-000000000005"
    op.execute(
        f"""
        INSERT INTO users (id, name, email, phone, password, role_id)
        SELECT
            '{buyer_id}',
            'Default Buyer',
            'buyer@example.com',
            '4444444444',
            'buyer123',
            id
        FROM roles
        WHERE name = 'buyer'
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'agent@example.com';")
    op.execute("DELETE FROM users WHERE email = 'buyer@example.com';")
