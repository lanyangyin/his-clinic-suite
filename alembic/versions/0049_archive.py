"""medical record archive

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "archive_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("archive_no", sa.String(30), nullable=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("record_type", sa.String(20), nullable=False, server_default="outpatient"),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("completeness", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("storage_location", sa.String(100), nullable=False, server_default=""),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("archived_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_archive_records_id", "archive_records", ["id"])
    op.create_index("ix_archive_records_archive_no", "archive_records", ["archive_no"], unique=True)

    op.create_table(
        "archive_borrowings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("archive_records.id"), nullable=False),
        sa.Column("borrower", sa.String(50), nullable=False),
        sa.Column("department", sa.String(50), nullable=False, server_default=""),
        sa.Column("purpose", sa.String(200), nullable=False, server_default=""),
        sa.Column("borrowed_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("returned_at", sa.DateTime(), nullable=True),
        sa.Column("approver", sa.String(50), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="borrowed"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_archive_borrowings_id", "archive_borrowings", ["id"])
    op.create_index("ix_archive_borrowings_record_id", "archive_borrowings", ["record_id"])

    op.create_table(
        "archive_copy_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("archive_records.id"), nullable=False),
        sa.Column("applicant", sa.String(50), nullable=False),
        sa.Column("id_number", sa.String(30), nullable=False, server_default=""),
        sa.Column("relationship", sa.String(30), nullable=False, server_default="本人"),
        sa.Column("purpose", sa.String(200), nullable=False, server_default=""),
        sa.Column("contents", sa.String(200), nullable=False, server_default=""),
        sa.Column("copies", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_archive_copy_requests_id", "archive_copy_requests", ["id"])
    op.create_index("ix_archive_copy_requests_record_id", "archive_copy_requests", ["record_id"])

    op.create_table(
        "archive_seals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("archive_records.id"), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("witness", sa.String(50), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_archive_seals_id", "archive_seals", ["id"])
    op.create_index("ix_archive_seals_record_id", "archive_seals", ["record_id"])

    op.create_table(
        "archive_destructions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("archive_records.id"), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("approved_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("destroyed_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_archive_destructions_id", "archive_destructions", ["id"])
    op.create_index("ix_archive_destructions_record_id", "archive_destructions", ["record_id"])


def downgrade():
    op.drop_table("archive_destructions")
    op.drop_table("archive_seals")
    op.drop_table("archive_copy_requests")
    op.drop_table("archive_borrowings")
    op.drop_table("archive_records")
