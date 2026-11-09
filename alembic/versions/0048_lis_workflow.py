"""LIS specimen workflow and structured results

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lab_items") as batch:
        batch.add_column(sa.Column("specimen_type", sa.String(30), nullable=False, server_default="血液"))
        batch.add_column(sa.Column("unit", sa.String(20), nullable=False, server_default=""))
        batch.add_column(sa.Column("reference_low", sa.Float(), nullable=True))
        batch.add_column(sa.Column("reference_high", sa.Float(), nullable=True))
        batch.add_column(sa.Column("method", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("tat_minutes", sa.Integer(), nullable=False, server_default="60"))
        batch.add_column(sa.Column("insurance_ratio", sa.Float(), nullable=False, server_default="0.7"))
        batch.add_column(sa.Column("result_kind", sa.String(10), nullable=False, server_default="numeric"))

    with op.batch_alter_table("lab_requests") as batch:
        batch.add_column(sa.Column("priority", sa.String(10), nullable=False, server_default="routine"))
        batch.add_column(sa.Column("specimen_no", sa.String(40), nullable=True))
        batch.add_column(sa.Column("specimen_type", sa.String(30), nullable=False, server_default="血液"))
        batch.add_column(sa.Column("collected_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("collected_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("received_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("received_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("testing_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("testing_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("report_no", sa.String(30), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("reviewed_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("reject_reason", sa.String(200), nullable=True))
        batch.add_column(sa.Column("result_value", sa.Float(), nullable=True))
        batch.add_column(sa.Column("result_unit", sa.String(20), nullable=False, server_default=""))
        batch.add_column(sa.Column("reference_low", sa.Float(), nullable=True))
        batch.add_column(sa.Column("reference_high", sa.Float(), nullable=True))
        batch.add_column(sa.Column("abnormal_flag", sa.String(10), nullable=False, server_default=""))
        batch.add_column(sa.Column("critical_flag", sa.Boolean(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("critical_note", sa.String(200), nullable=True))
        batch.add_column(sa.Column("critical_notified_to", sa.String(100), nullable=True))
        batch.add_column(sa.Column("critical_notified_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_lab_requests_specimen_no", ["specimen_no"], unique=False)


def downgrade():
    with op.batch_alter_table("lab_requests") as batch:
        batch.drop_index("ix_lab_requests_specimen_no")
        for column in (
            "critical_notified_at",
            "critical_notified_to",
            "critical_note",
            "critical_flag",
            "abnormal_flag",
            "reference_high",
            "reference_low",
            "result_unit",
            "result_value",
            "reject_reason",
            "reviewed_by",
            "reviewed_at",
            "report_no",
            "testing_by",
            "testing_at",
            "received_by",
            "received_at",
            "collected_by",
            "collected_at",
            "specimen_type",
            "specimen_no",
            "priority",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("lab_items") as batch:
        for column in (
            "result_kind",
            "insurance_ratio",
            "tat_minutes",
            "method",
            "reference_high",
            "reference_low",
            "unit",
            "specimen_type",
        ):
            batch.drop_column(column)
