"""finance reconciliation

Revision ID: 0146
Revises: 0145
"""
import sqlalchemy as sa
from alembic import op
revision = "0146"
down_revision = "0145"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "financial_reconciliations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("biz_date", sa.String(10), nullable=False, unique=True),
        sa.Column("total_payment", sa.Float(), nullable=False),
        sa.Column("total_inpatient", sa.Float(), nullable=False),
        sa.Column("total_refund", sa.Float(), nullable=False),
        sa.Column("net", sa.Float(), nullable=False),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table("financial_reconciliations")
