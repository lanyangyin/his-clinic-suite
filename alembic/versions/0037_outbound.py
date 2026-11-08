"""warehouse outbound orders (pharmacy requisition)

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outbound_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("outbound_no", sa.String(30), nullable=False),
        # requisition 领用 / transfer 调拨 / scrap 报损 / return 退库
        sa.Column("outbound_type", sa.String(20), nullable=False, server_default="requisition"),
        # pharmacy 药房 / department 科室
        sa.Column("target_type", sa.String(20), nullable=False, server_default="pharmacy"),
        sa.Column("target_name", sa.String(50), nullable=False, server_default="药房"),
        sa.Column("applicant", sa.String(50), nullable=False, server_default=""),
        sa.Column("approver", sa.String(50), nullable=False, server_default=""),
        sa.Column("issuer", sa.String(50), nullable=False, server_default=""),
        # submitted 已申请 / approved 已审核 / issued 已出库 / cancelled 已取消
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("outbound_no"),
    )
    op.create_index("ix_outbound_orders_id", "outbound_orders", ["id"])

    op.create_table(
        "outbound_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("outbound_orders.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="drug"),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(60), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("insurance_code", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_outbound_items_id", "outbound_items", ["id"])
    op.create_index("ix_outbound_items_order_id", "outbound_items", ["order_id"])


def downgrade():
    op.drop_index("ix_outbound_items_order_id", table_name="outbound_items")
    op.drop_index("ix_outbound_items_id", table_name="outbound_items")
    op.drop_table("outbound_items")
    op.drop_index("ix_outbound_orders_id", table_name="outbound_orders")
    op.drop_table("outbound_orders")
