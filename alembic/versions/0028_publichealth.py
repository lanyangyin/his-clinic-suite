"""add disease reports (public health)

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "disease_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False
        ),
        sa.Column("disease_code", sa.String(20), nullable=False),
        sa.Column("disease_name", sa.String(100), nullable=False),
        # draft 草稿 / submitted 已上报
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reported_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "encounter_id", "disease_code", name="uq_disease_report"
        ),
    )
    op.create_index("ix_disease_reports_id", "disease_reports", ["id"])
    op.create_index(
        "ix_disease_reports_encounter_id", "disease_reports", ["encounter_id"]
    )


def downgrade():
    op.drop_index("ix_disease_reports_encounter_id", table_name="disease_reports")
    op.drop_index("ix_disease_reports_id", table_name="disease_reports")
    op.drop_table("disease_reports")
