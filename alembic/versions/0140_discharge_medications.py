"""discharge medications

Revision ID: 0140
Revises: 0139
"""
import sqlalchemy as sa
from alembic import op
revision = "0140"
down_revision = "0139"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "discharge_medications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admission_id", sa.Integer(), nullable=False),
        sa.Column("drug_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("directions", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_discharge_medications_admission_id", "discharge_medications", ["admission_id"])

def downgrade():
    op.drop_index("ix_discharge_medications_admission_id", table_name="discharge_medications")
    op.drop_table("discharge_medications")
