"""allow multiple encounters per registration (return visit)

Revision ID: 0155
Revises: 0154
"""
from alembic import op
revision = "0155"
down_revision = "0154"
branch_labels = None
depends_on = None

def upgrade():
    op.drop_index("ix_encounters_registration_id", table_name="encounters")
    op.create_index(
        "ix_encounters_registration_id", "encounters", ["registration_id"], unique=False
    )

def downgrade():
    op.drop_index("ix_encounters_registration_id", table_name="encounters")
    op.create_index(
        "ix_encounters_registration_id", "encounters", ["registration_id"], unique=True
    )
