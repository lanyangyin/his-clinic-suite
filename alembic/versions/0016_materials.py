"""add material tables: material_items, material_stocks, material_usages

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "material_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(50), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_high_value", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_material_items_id", "material_items", ["id"])

    op.create_table(
        "material_stocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=False),
        sa.Column("warehouse", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("item_id", "warehouse", name="uq_material_item_warehouse"),
    )
    op.create_index("ix_material_stocks_id", "material_stocks", ["id"])
    op.create_index("ix_material_stocks_item_id", "material_stocks", ["item_id"])

    op.create_table(
        "material_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=False),
        sa.Column("serial_no", sa.String(50), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default=""),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.Column("used_by", sa.String(50), nullable=False, server_default=""),
        sa.UniqueConstraint("serial_no"),
    )
    op.create_index("ix_material_usages_id", "material_usages", ["id"])
    op.create_index("ix_material_usages_item_id", "material_usages", ["item_id"])


def downgrade():
    op.drop_index("ix_material_usages_item_id", table_name="material_usages")
    op.drop_index("ix_material_usages_id", table_name="material_usages")
    op.drop_table("material_usages")
    op.drop_index("ix_material_stocks_item_id", table_name="material_stocks")
    op.drop_index("ix_material_stocks_id", table_name="material_stocks")
    op.drop_table("material_stocks")
    op.drop_index("ix_material_items_id", table_name="material_items")
    op.drop_table("material_items")
