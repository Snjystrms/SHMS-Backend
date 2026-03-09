"""add 10 default boats for default boat owner

Revision ID: 20260309_02
Revises: 20260309_01
Create Date: 2026-03-09
"""

from alembic import op

revision = "20260309_02"
down_revision = "20260309_01"
branch_labels = None
depends_on = None

BOAT_OWNER_ID = "00000000-0000-4000-a000-000000000003"

BOATS = [
    ("00000000-0000-4000-b000-000000000001", "MH-01", "Sea Voyager",    "trawler",       "mumbai"),
    ("00000000-0000-4000-b000-000000000002", "MH-02", "Ocean Pearl",    "gillnetter",    "mumbai"),
    ("00000000-0000-4000-b000-000000000003", "MH-03", "Blue Horizon",   "trawler",       "mumbai"),
    ("00000000-0000-4000-b000-000000000004", "MH-04", "Star Fisher",    "purse_seiner",  "ratnagiri"),
    ("00000000-0000-4000-b000-000000000005", "MH-05", "Wave Rider",     "gillnetter",    "ratnagiri"),
    ("00000000-0000-4000-b000-000000000006", "MH-06", "Deep Catch",     "trawler",       "mumbai"),
    ("00000000-0000-4000-b000-000000000007", "MH-07", "Golden Tide",    "purse_seiner",  "mumbai"),
    ("00000000-0000-4000-b000-000000000008", "MH-08", "Silver Marlin",  "gillnetter",    "ratnagiri"),
    ("00000000-0000-4000-b000-000000000009", "MH-09", "Coastal King",   "trawler",       "mumbai"),
    ("00000000-0000-4000-b000-000000000010", "MH-10", "Harbor Queen",   "purse_seiner",  "ratnagiri"),
]


def upgrade() -> None:
    for boat_id, number, name, boat_type, harbor in BOATS:
        op.execute(
            f"""
            INSERT INTO boats (id, boat_owner_id, boat_number, boat_name, boat_type, harbor_name, is_register)
            VALUES (
                '{boat_id}',
                '{BOAT_OWNER_ID}',
                '{number}',
                '{name}',
                '{boat_type}',
                '{harbor}',
                true
            )
            ON CONFLICT (id) DO NOTHING;
            """
        )


def downgrade() -> None:
    ids = ", ".join(f"'{b[0]}'" for b in BOATS)
    op.execute(f"DELETE FROM boats WHERE id IN ({ids});")
