"""patient merge requests

Revision ID: 0134
Revises: 0133
"""
import sqlalchemy as sa
from alembic import op
revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "patient_merge_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("review_note", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_patient_merge_requests_source_id", "patient_merge_requests", ["source_id"])
    op.create_index("ix_patient_merge_requests_target_id", "patient_merge_requests", ["target_id"])
    op.create_index("ix_patient_merge_requests_status", "patient_merge_requests", ["status"])

def downgrade():
    op.drop_index("ix_patient_merge_requests_status", table_name="patient_merge_requests")
    op.drop_index("ix_patient_merge_requests_target_id", table_name="patient_merge_requests")
    op.drop_index("ix_patient_merge_requests_source_id", table_name="patient_merge_requests")
    op.drop_table("patient_merge_requests")
