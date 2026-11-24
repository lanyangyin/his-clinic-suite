"""financial vouchers

Revision ID: 0145
Revises: 0144
"""
import sqlalchemy as sa
from alembic import op
revision = "0145"
down_revision = "0144"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "financial_vouchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("voucher_no", sa.String(40), nullable=False, unique=True),
        sa.Column("biz_type", sa.String(20), nullable=False),
        sa.Column("biz_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table("financial_vouchers")
