"""notification outbox and narcotic inventory checks

Revision ID: 0098
Revises: 0097
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("biz_type", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("biz_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="internal"),
        sa.Column("recipient", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"])
    op.create_table(
        "narcotic_inventory_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("drug_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("batch_no", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("expected_qty", sa.Integer(), nullable=False),
        sa.Column("counted_qty", sa.Integer(), nullable=False),
        sa.Column("difference", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("checked_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("approved_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_narcotic_inventory_checks_drug_id", "narcotic_inventory_checks", ["drug_id"])
    op.create_index("ix_narcotic_inventory_checks_status", "narcotic_inventory_checks", ["status"])


def downgrade():
    op.drop_index("ix_narcotic_inventory_checks_status", table_name="narcotic_inventory_checks")
    op.drop_index("ix_narcotic_inventory_checks_drug_id", table_name="narcotic_inventory_checks")
    op.drop_table("narcotic_inventory_checks")
    op.drop_index("ix_notification_outbox_status", table_name="notification_outbox")
    op.drop_table("notification_outbox")
