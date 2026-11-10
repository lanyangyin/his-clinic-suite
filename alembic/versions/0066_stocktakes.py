"""drug and material stocktakes

Revision ID: 0066
Revises: 0065
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stocktakes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("take_no", sa.String(30), nullable=False, unique=True),
        sa.Column("title", sa.String(100), nullable=False, server_default=""),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="总库"),
        sa.Column("status", sa.String(20), nullable=False, server_default="counting"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_stocktakes_id", "stocktakes", ["id"])

    op.create_table(
        "stocktake_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("take_id", sa.Integer(), sa.ForeignKey("stocktakes.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(60), nullable=False, server_default=""),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="总库"),
        sa.Column("book_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_quantity", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_stocktake_items_id", "stocktake_items", ["id"])
    op.create_index("ix_stocktake_items_take_id", "stocktake_items", ["take_id"])


def downgrade():
    op.drop_table("stocktake_items")
    op.drop_table("stocktakes")
