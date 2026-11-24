"""patient merge audit

Revision ID: 0125
Revises: 0124
"""
import sqlalchemy as sa
from alembic import op
revision = "0125"
down_revision = "0124"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "patient_merge_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False, server_default=""),
        sa.Column("merged_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_patient_merge_logs_source_id", "patient_merge_logs", ["source_id"])
    op.create_index("ix_patient_merge_logs_target_id", "patient_merge_logs", ["target_id"])

def downgrade():
    op.drop_index("ix_patient_merge_logs_target_id", table_name="patient_merge_logs")
    op.drop_index("ix_patient_merge_logs_source_id", table_name="patient_merge_logs")
    op.drop_table("patient_merge_logs")
