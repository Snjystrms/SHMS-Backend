"""merge_heads

Revision ID: 5da154916a6e
Revises: 20260225_04, 20260309_04
Create Date: 2026-03-09 16:52:03.284471
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5da154916a6e'
down_revision: Union[str, None] = ('20260225_04', '20260309_04')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
