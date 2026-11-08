"""inbound receiving + insurance drug catalog + item master extensions

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade():
    # ---- 药品主数据扩展（医保贯标/生产信息）----
    with op.batch_alter_table("drugs") as batch:
        batch.add_column(sa.Column("insurance_code", sa.String(40), nullable=False, server_default=""))
        batch.add_column(sa.Column("approval_no", sa.String(60), nullable=False, server_default=""))
        batch.add_column(sa.Column("manufacturer", sa.String(100), nullable=False, server_default=""))
        batch.add_column(sa.Column("dosage_form", sa.String(30), nullable=False, server_default=""))

    # ---- 物资主数据扩展（器械/耗材/办公分类与注册证）----
    with op.batch_alter_table("material_items") as batch:
        batch.add_column(sa.Column("category", sa.String(20), nullable=False, server_default="consumable"))
        batch.add_column(sa.Column("manufacturer", sa.String(100), nullable=False, server_default=""))
        batch.add_column(sa.Column("registration_no", sa.String(60), nullable=False, server_default=""))

    # ---- 入库单（独立于药房发药）----
    op.create_table(
        "inbound_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_no", sa.String(30), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False, server_default="drug"),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="purchase"),
        # received 已收货 / checked 已验收 / stocked 已入库 / cancelled 已取消
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("delivery_no", sa.String(50), nullable=False, server_default=""),
        sa.Column("invoice_no", sa.String(50), nullable=False, server_default=""),
        sa.Column("received_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("checked_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("stocked_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("order_no"),
    )
    op.create_index("ix_inbound_orders_id", "inbound_orders", ["id"])

    op.create_table(
        "inbound_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("inbound_orders.id"), nullable=False),
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
        sa.Column("registration_no", sa.String(60), nullable=False, server_default=""),
        sa.Column("manufacturer", sa.String(100), nullable=False, server_default=""),
        sa.Column("storage_condition", sa.String(20), nullable=False, server_default=""),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="总库"),
        sa.Column("location", sa.String(20), nullable=False, server_default=""),
        sa.Column("rejected_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reject_reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inbound_items_id", "inbound_items", ["id"])
    op.create_index("ix_inbound_items_order_id", "inbound_items", ["order_id"])

    # ---- 医保药品目录（贯标码/甲乙类）----
    op.create_table(
        "insurance_drugs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("national_code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("dosage_form", sa.String(30), nullable=False, server_default=""),
        sa.Column("spec", sa.String(60), nullable=False, server_default=""),
        sa.Column("manufacturer", sa.String(100), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        # 甲 / 乙 / 丙（丙=目录外自费，供演示）
        sa.Column("category", sa.String(10), nullable=False, server_default="乙"),
        sa.Column("reimbursement_note", sa.String(200), nullable=False, server_default=""),
        sa.Column("approval_no", sa.String(60), nullable=False, server_default=""),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_version", sa.String(30), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("national_code"),
    )
    op.create_index("ix_insurance_drugs_id", "insurance_drugs", ["id"])
    op.create_index("ix_insurance_drugs_name", "insurance_drugs", ["name"])

    op.create_table(
        "insurance_catalog_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("file_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(64), nullable=False, server_default=""),
        sa.Column("imported_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_insurance_catalog_versions_id", "insurance_catalog_versions", ["id"])


def downgrade():
    op.drop_index("ix_insurance_catalog_versions_id", table_name="insurance_catalog_versions")
    op.drop_table("insurance_catalog_versions")
    op.drop_index("ix_insurance_drugs_name", table_name="insurance_drugs")
    op.drop_index("ix_insurance_drugs_id", table_name="insurance_drugs")
    op.drop_table("insurance_drugs")
    op.drop_index("ix_inbound_items_order_id", table_name="inbound_items")
    op.drop_index("ix_inbound_items_id", table_name="inbound_items")
    op.drop_table("inbound_items")
    op.drop_index("ix_inbound_orders_id", table_name="inbound_orders")
    op.drop_table("inbound_orders")
    with op.batch_alter_table("material_items") as batch:
        batch.drop_column("registration_no")
        batch.drop_column("manufacturer")
        batch.drop_column("category")
    with op.batch_alter_table("drugs") as batch:
        batch.drop_column("dosage_form")
        batch.drop_column("manufacturer")
        batch.drop_column("approval_no")
        batch.drop_column("insurance_code")
