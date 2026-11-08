"""add suppliers and purchase records

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("contact", sa.String(50), nullable=False, server_default=""),
        sa.Column("phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("address", sa.String(200), nullable=False, server_default=""),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_suppliers_id", "suppliers", ["id"])

    op.create_table(
        "purchase_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True
        ),
        sa.Column("purchased_at", sa.DateTime(), nullable=False),
        sa.Column("purchased_by", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index("ix_purchase_records_id", "purchase_records", ["id"])
    op.create_index("ix_purchase_records_drug_id", "purchase_records", ["drug_id"])


def downgrade():
    op.drop_index("ix_purchase_records_drug_id", table_name="purchase_records")
    op.drop_index("ix_purchase_records_id", table_name="purchase_records")
    op.drop_table("purchase_records")
    op.drop_index("ix_suppliers_id", table_name="suppliers")
    op.drop_table("suppliers")
