"""partial outbound + stock adjustments

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("outbound_items") as batch:
        batch.add_column(
            sa.Column("issued_quantity", sa.Integer(), nullable=False, server_default="0")
        )

    op.create_table(
        "stock_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adjust_no", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="drug"),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("expected_quantity", sa.Integer(), nullable=False),
        sa.Column("actual_quantity", sa.Integer(), nullable=False),
        sa.Column("diff", sa.Integer(), nullable=False),
        # in 盘盈 / out 盘亏
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("check_id", sa.Integer(), sa.ForeignKey("warehouse_checks.id"), nullable=True),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("adjust_no"),
    )
    op.create_index("ix_stock_adjustments_id", "stock_adjustments", ["id"])


def downgrade():
    op.drop_index("ix_stock_adjustments_id", table_name="stock_adjustments")
    op.drop_table("stock_adjustments")
    with op.batch_alter_table("outbound_items") as batch:
        batch.drop_column("issued_quantity")
