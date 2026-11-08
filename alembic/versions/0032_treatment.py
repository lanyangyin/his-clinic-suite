"""add prescription dosage and treatment orders

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("prescription_items") as batch:
        batch.add_column(
            sa.Column("dosage", sa.String(50), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("frequency", sa.String(20), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("route", sa.String(20), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("days", sa.Integer(), nullable=False, server_default="1")
        )

    op.create_table(
        "treatment_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False
        ),
        sa.Column(
            "charge_item_id", sa.Integer(), sa.ForeignKey("charge_items.id"), nullable=False
        ),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        # pending 待执行 / done 已执行 / cancelled 已取消
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("ordered_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("ordered_at", sa.DateTime(), nullable=False),
        sa.Column("executed_by", sa.String(50), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_treatment_orders_id", "treatment_orders", ["id"])
    op.create_index(
        "ix_treatment_orders_encounter_id", "treatment_orders", ["encounter_id"]
    )


def downgrade():
    op.drop_index("ix_treatment_orders_encounter_id", table_name="treatment_orders")
    op.drop_index("ix_treatment_orders_id", table_name="treatment_orders")
    op.drop_table("treatment_orders")
    with op.batch_alter_table("prescription_items") as batch:
        batch.drop_column("days")
        batch.drop_column("route")
        batch.drop_column("frequency")
        batch.drop_column("dosage")
