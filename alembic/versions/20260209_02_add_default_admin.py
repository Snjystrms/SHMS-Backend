"""add default admin user

Revision ID: 20260209_02
Revises: 20260209_01
Create Date: 2026-02-09
"""

from alembic import op
import uuid

# revision identifiers, used by Alembic.
revision = "20260209_02"
down_revision = "20260209_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use a fixed UUID for the default admin to prevent duplicates/enable easy referencing
    admin_id = "00000000-0000-4000-a000-000000000001"
    
    op.execute(
        f"""
        INSERT INTO users (id, name, email, phone, password, role_id)
        SELECT 
            '{admin_id}', 
            'Default Admin', 
            'admin@example.com', 
            '0000000000', 
            'admin123', 
            id 
        FROM roles 
        WHERE name = 'admin'
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'admin@example.com';")
