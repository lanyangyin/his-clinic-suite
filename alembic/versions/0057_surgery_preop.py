"""surgery preop and anesthesia

Revision ID: 0057
Revises: 0056
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "surgery_preop_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("surgery_cases.id"), nullable=False, unique=True),
        sa.Column("anesthesiologist", sa.String(50), nullable=False, server_default=""),
        sa.Column("asa_grade", sa.String(5), nullable=False, server_default=""),
        sa.Column("airway", sa.String(100), nullable=False, server_default=""),
        sa.Column("allergies", sa.String(200), nullable=False, server_default=""),
        sa.Column("comorbidities", sa.String(300), nullable=False, server_default=""),
        sa.Column("fasting", sa.String(100), nullable=False, server_default=""),
        sa.Column("consent", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("assessment", sa.String(1000), nullable=False, server_default=""),
        sa.Column("plan", sa.String(500), nullable=False, server_default=""),
        sa.Column("risk", sa.String(20), nullable=False, server_default="low"),
        sa.Column("assessed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("assessed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_surgery_preop_assessments_id", "surgery_preop_assessments", ["id"])

    op.create_table(
        "anesthesia_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("surgery_cases.id"), nullable=False, unique=True),
        sa.Column("anesthesia_type", sa.String(30), nullable=False, server_default=""),
        sa.Column("anesthesiologist", sa.String(50), nullable=False, server_default=""),
        sa.Column("airway", sa.String(100), nullable=False, server_default=""),
        sa.Column("agents", sa.String(500), nullable=False, server_default=""),
        sa.Column("monitors", sa.String(200), nullable=False, server_default=""),
        sa.Column("vitals", sa.String(500), nullable=False, server_default=""),
        sa.Column("fluids_ml", sa.Integer(), nullable=True),
        sa.Column("blood_loss_ml", sa.Integer(), nullable=True),
        sa.Column("urine_ml", sa.Integer(), nullable=True),
        sa.Column("complications", sa.String(200), nullable=False, server_default=""),
        sa.Column("notes", sa.String(500), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("recorded_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_anesthesia_records_id", "anesthesia_records", ["id"])


def downgrade():
    op.drop_table("anesthesia_records")
    op.drop_table("surgery_preop_assessments")
