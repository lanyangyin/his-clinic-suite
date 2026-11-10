"""archive destruction approval workflow

Revision ID: 0076
Revises: 0075
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "archive_destruction_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "record_id",
            sa.Integer(),
            sa.ForeignKey("archive_records.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column(
            "requested_by", sa.String(50), nullable=False, server_default=""
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("approver", sa.String(50), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "approval_note", sa.String(200), nullable=False, server_default=""
        ),
        sa.Column(
            "executed_by", sa.String(50), nullable=False, server_default=""
        ),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("witness", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_archive_destruction_requests_id",
        "archive_destruction_requests",
        ["id"],
    )
    op.create_index(
        "ix_archive_destruction_requests_record_id",
        "archive_destruction_requests",
        ["record_id"],
    )


def downgrade():
    op.drop_table("archive_destruction_requests")
