"""pharmacy retail sales + drug otc flag

Revision ID: 0079
Revises: 0078
Create Date: 2026-11-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drugs") as batch:
        batch.add_column(
            sa.Column("is_otc", sa.Boolean(), nullable=False, server_default="0")
        )

    op.create_table(
        "retail_sales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_no", sa.String(30), nullable=False, unique=True),
        sa.Column("customer_name", sa.String(50), nullable=False, server_default=""),
        sa.Column("phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("channel", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="completed"
        ),
        sa.Column("sold_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("refunded_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "retail_sale_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sale_id",
            sa.Integer(),
            sa.ForeignKey("retail_sales.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("material_items.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(60), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="药房"),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("retail_sale_items")
    op.drop_table("retail_sales")
    with op.batch_alter_table("drugs") as batch:
        batch.drop_column("is_otc")
