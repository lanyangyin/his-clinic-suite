"""purchase requests for outbound shortage

Revision ID: 0051
Revises: 0050
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_no", sa.String(30), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("department", sa.String(50), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("requester", sa.String(50), nullable=False, server_default=""),
        sa.Column("approver", sa.String(50), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_reason", sa.String(200), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("ordered_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_purchase_requests_id", "purchase_requests", ["id"])
    op.create_index("ix_purchase_requests_request_no", "purchase_requests", ["request_no"], unique=True)

    op.create_table(
        "purchase_request_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("purchase_requests.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="drug"),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(60), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_purchase_request_items_id", "purchase_request_items", ["id"])
    op.create_index("ix_purchase_request_items_request_id", "purchase_request_items", ["request_id"])

    with op.batch_alter_table("outbound_orders") as batch:
        batch.add_column(sa.Column("purchase_request_id", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("outbound_orders") as batch:
        batch.drop_column("purchase_request_id")
    op.drop_table("purchase_request_items")
    op.drop_table("purchase_requests")
