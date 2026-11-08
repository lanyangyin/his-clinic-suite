"""add warehouse tables: warehouse_stocks, warehouse_checks

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "warehouse_stocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("drug_id", "batch_no", name="uq_warehouse_drug_batch"),
    )
    op.create_index("ix_warehouse_stocks_id", "warehouse_stocks", ["id"])
    op.create_index("ix_warehouse_stocks_drug_id", "warehouse_stocks", ["drug_id"])

    op.create_table(
        "warehouse_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False),
        sa.Column("expected_quantity", sa.Integer(), nullable=False),
        sa.Column("actual_quantity", sa.Integer(), nullable=False),
        sa.Column("diff", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("checked_by", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index("ix_warehouse_checks_id", "warehouse_checks", ["id"])
    op.create_index("ix_warehouse_checks_drug_id", "warehouse_checks", ["drug_id"])


def downgrade():
    op.drop_index("ix_warehouse_checks_drug_id", table_name="warehouse_checks")
    op.drop_index("ix_warehouse_checks_id", table_name="warehouse_checks")
    op.drop_table("warehouse_checks")
    op.drop_index("ix_warehouse_stocks_drug_id", table_name="warehouse_stocks")
    op.drop_index("ix_warehouse_stocks_id", table_name="warehouse_stocks")
    op.drop_table("warehouse_stocks")
