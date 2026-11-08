"""add charge items and encounter charges

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "charge_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        # registration 挂号 / consultation 诊疗 / lab 检验 / imaging 检查 / treatment 治疗 / other 其他
        sa.Column("category", sa.String(20), nullable=False, server_default="other"),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("insurance_ratio", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_charge_items_id", "charge_items", ["id"])

    op.create_table(
        "encounter_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False
        ),
        # 来源：registration / encounter / prescription / lab_request / imaging_request / treatment
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("charge_type", sa.String(20), nullable=False),
        sa.Column(
            "charge_item_id", sa.Integer(), sa.ForeignKey("charge_items.id"), nullable=True
        ),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("insurance_ratio", sa.Float(), nullable=False, server_default="0.7"),
        # pending 待收 / paid 已收 / refunded 已退
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", name="uq_charge_source"),
    )
    op.create_index("ix_encounter_charges_id", "encounter_charges", ["id"])
    op.create_index(
        "ix_encounter_charges_encounter_id", "encounter_charges", ["encounter_id"]
    )


def downgrade():
    op.drop_index("ix_encounter_charges_encounter_id", table_name="encounter_charges")
    op.drop_index("ix_encounter_charges_id", table_name="encounter_charges")
    op.drop_table("encounter_charges")
    op.drop_index("ix_charge_items_id", table_name="charge_items")
    op.drop_table("charge_items")
