"""add drug_stocks table

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drug_stocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("location", sa.String(20), nullable=False, server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint("drug_id", "batch_no", name="uq_drug_stocks_drug_batch"),
    )
    op.create_index("ix_drug_stocks_id", "drug_stocks", ["id"])
    op.create_index("ix_drug_stocks_drug_id", "drug_stocks", ["drug_id"])


def downgrade():
    op.drop_index("ix_drug_stocks_drug_id", table_name="drug_stocks")
    op.drop_index("ix_drug_stocks_id", table_name="drug_stocks")
    op.drop_table("drug_stocks")
