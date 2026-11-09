"""TCM prescriptions and decoction room

Revision ID: 0052
Revises: 0051
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tcm_herbs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(60), nullable=False, server_default=""),
        sa.Column("unit", sa.String(10), nullable=False, server_default="g"),
        sa.Column("price_per_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("insurance_code", sa.String(40), nullable=False, server_default=""),
        sa.Column("toxicity", sa.String(20), nullable=False, server_default="none"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tcm_herbs_id", "tcm_herbs", ["id"])
    op.create_index("ix_tcm_herbs_code", "tcm_herbs", ["code"], unique=True)

    op.create_table(
        "tcm_prescriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prescription_no", sa.String(30), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("doctor", sa.String(50), nullable=False, server_default=""),
        sa.Column("formula_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("usage", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("packs", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("decoct_service", sa.String(10), nullable=False, server_default="decoct"),
        sa.Column("decoction_method", sa.String(50), nullable=False, server_default="常规煎煮"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("review_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("dispense_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("dispensed_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tcm_prescriptions_id", "tcm_prescriptions", ["id"])
    op.create_index("ix_tcm_prescriptions_prescription_no", "tcm_prescriptions", ["prescription_no"], unique=True)
    op.create_index("ix_tcm_prescriptions_encounter_id", "tcm_prescriptions", ["encounter_id"])

    op.create_table(
        "tcm_prescription_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("tcm_prescriptions.id"), nullable=False),
        sa.Column("herb_id", sa.Integer(), sa.ForeignKey("tcm_herbs.id"), nullable=False),
        sa.Column("herb_name", sa.String(100), nullable=False),
        sa.Column("dose_g", sa.Float(), nullable=False),
        sa.Column("special", sa.String(20), nullable=False, server_default="none"),
        sa.Column("note", sa.String(100), nullable=False, server_default=""),
    )
    op.create_index("ix_tcm_prescription_items_id", "tcm_prescription_items", ["id"])
    op.create_index("ix_tcm_prescription_items_prescription_id", "tcm_prescription_items", ["prescription_id"])

    op.create_table(
        "decoction_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_no", sa.String(30), nullable=False),
        sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("tcm_prescriptions.id"), nullable=False, unique=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_name", sa.String(50), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("soak_minutes", sa.Integer(), nullable=True),
        sa.Column("decoct_minutes", sa.Integer(), nullable=True),
        sa.Column("machine_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("bags", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bag_volume_ml", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("soaked_at", sa.DateTime(), nullable=True),
        sa.Column("decocted_at", sa.DateTime(), nullable=True),
        sa.Column("packaged_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("pickup_method", sa.String(20), nullable=False, server_default="self"),
        sa.Column("receiver", sa.String(50), nullable=False, server_default=""),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_decoction_orders_id", "decoction_orders", ["id"])
    op.create_index("ix_decoction_orders_order_no", "decoction_orders", ["order_no"], unique=True)
    op.create_index("ix_decoction_orders_encounter_id", "decoction_orders", ["encounter_id"])

    op.create_table(
        "decoction_bags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("decoction_orders.id"), nullable=False),
        sa.Column("bag_no", sa.String(50), nullable=False),
        sa.Column("expiry", sa.DateTime(), nullable=True),
        sa.Column("label", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_decoction_bags_id", "decoction_bags", ["id"])
    op.create_index("ix_decoction_bags_order_id", "decoction_bags", ["order_id"])


def downgrade():
    op.drop_table("decoction_bags")
    op.drop_table("decoction_orders")
    op.drop_table("tcm_prescription_items")
    op.drop_table("tcm_prescriptions")
    op.drop_table("tcm_herbs")
