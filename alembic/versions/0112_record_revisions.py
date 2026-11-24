"""medical record revision requests

Revision ID: 0112
Revises: 0111
"""
import sqlalchemy as sa
from alembic import op

revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "medical_record_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("review_note", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_medical_record_revisions_encounter_id", "medical_record_revisions", ["encounter_id"])


def downgrade():
    op.drop_index("ix_medical_record_revisions_encounter_id", table_name="medical_record_revisions")
    op.drop_table("medical_record_revisions")
