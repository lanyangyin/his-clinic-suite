"""treatment follow-ups and daily report

Revision ID: 0059
Revises: 0058
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "treatment_follow_ups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("treatment_room_cases.id"), nullable=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False, server_default="换药"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_treatment_follow_ups_id", "treatment_follow_ups", ["id"])
    op.create_index("ix_treatment_follow_ups_patient_id", "treatment_follow_ups", ["patient_id"])
    op.create_index("ix_treatment_follow_ups_due_date", "treatment_follow_ups", ["due_date"])


def downgrade():
    op.drop_table("treatment_follow_ups")
