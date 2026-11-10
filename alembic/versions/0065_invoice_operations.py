"""invoice void / print / usage

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("invoice_status", sa.String(20), nullable=False, server_default="normal"))
        batch.add_column(sa.Column("invoice_print_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("invoice_printed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("invoice_voided_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("invoice_voided_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("invoice_void_reason", sa.String(200), nullable=False, server_default=""))

    op.create_table(
        "invoice_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("invoice_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_invoice_operations_id", "invoice_operations", ["id"])
    op.create_index("ix_invoice_operations_payment_id", "invoice_operations", ["payment_id"])


def downgrade():
    op.drop_table("invoice_operations")
    with op.batch_alter_table("payments") as batch:
        batch.drop_column("invoice_void_reason")
        batch.drop_column("invoice_voided_by")
        batch.drop_column("invoice_voided_at")
        batch.drop_column("invoice_printed_at")
        batch.drop_column("invoice_print_count")
        batch.drop_column("invoice_status")
