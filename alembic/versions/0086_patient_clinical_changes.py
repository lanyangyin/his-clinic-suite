"""patient clinical changes audit

Revision ID: 0086
Revises: 0085
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "patient_clinical_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("field", sa.String(30), nullable=False),
        sa.Column("old_value", sa.String(500), nullable=False, server_default=""),
        sa.Column("new_value", sa.String(500), nullable=False, server_default=""),
        sa.Column("reason", sa.String(300), nullable=False, server_default=""),
        sa.Column("changed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("patient_clinical_changes")
