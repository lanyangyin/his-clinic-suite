"""inpatient payments

Revision ID: 0143
Revises: 0142
"""
import sqlalchemy as sa
from alembic import op
revision = "0143"
down_revision = "0142"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "inpatient_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admission_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inpatient_payments_admission_id", "inpatient_payments", ["admission_id"])

def downgrade():
    op.drop_index("ix_inpatient_payments_admission_id", table_name="inpatient_payments")
    op.drop_table("inpatient_payments")
