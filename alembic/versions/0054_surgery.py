"""operating room and surgery workflow

Revision ID: 0054
Revises: 0053
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operating_rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("location", sa.String(100), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_operating_rooms_id", "operating_rooms", ["id"])
    op.create_index("ix_operating_rooms_code", "operating_rooms", ["code"], unique=True)

    op.create_table(
        "surgery_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("surgery_no", sa.String(30), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("operating_rooms.id"), nullable=True),
        sa.Column("procedure_name", sa.String(100), nullable=False),
        sa.Column("diagnosis", sa.String(200), nullable=False, server_default=""),
        sa.Column("surgeon", sa.String(50), nullable=False, server_default=""),
        sa.Column("anesthesia_type", sa.String(30), nullable=False, server_default=""),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_surgery_cases_id", "surgery_cases", ["id"])
    op.create_index("ix_surgery_cases_surgery_no", "surgery_cases", ["surgery_no"], unique=True)
    op.create_index("ix_surgery_cases_patient_id", "surgery_cases", ["patient_id"])

    op.create_table(
        "surgery_safety_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("surgery_cases.id"), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("checklist", sa.String(500), nullable=False, server_default=""),
        sa.Column("completed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_surgery_safety_checks_id", "surgery_safety_checks", ["id"])
    op.create_index("ix_surgery_safety_checks_case_id", "surgery_safety_checks", ["case_id"])

    op.create_table(
        "surgery_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("surgery_cases.id"), nullable=False),
        sa.Column("findings", sa.String(500), nullable=False, server_default=""),
        sa.Column("procedure_detail", sa.String(1000), nullable=False, server_default=""),
        sa.Column("implants", sa.String(200), nullable=False, server_default=""),
        sa.Column("specimens", sa.String(200), nullable=False, server_default=""),
        sa.Column("blood_loss_ml", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=False, server_default=""),
        sa.Column("recorded_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_surgery_records_id", "surgery_records", ["id"])
    op.create_index("ix_surgery_records_case_id", "surgery_records", ["case_id"])

    op.create_table(
        "surgery_instrument_counts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("surgery_cases.id"), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("expected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("counted_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("counted_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_surgery_instrument_counts_id", "surgery_instrument_counts", ["id"])
    op.create_index("ix_surgery_instrument_counts_case_id", "surgery_instrument_counts", ["case_id"])

    op.create_table(
        "surgery_recoveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("surgery_cases.id"), nullable=False),
        sa.Column("pacu_in", sa.DateTime(), nullable=True),
        sa.Column("pacu_out", sa.DateTime(), nullable=True),
        sa.Column("vitals", sa.String(200), nullable=False, server_default=""),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("nurse", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
    )
    op.create_index("ix_surgery_recoveries_id", "surgery_recoveries", ["id"])
    op.create_index("ix_surgery_recoveries_case_id", "surgery_recoveries", ["case_id"])

    with op.batch_alter_table("instrument_packages") as batch:
        batch.add_column(sa.Column("surgery_case_id", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("instrument_packages") as batch:
        batch.drop_column("surgery_case_id")
    op.drop_table("surgery_recoveries")
    op.drop_table("surgery_instrument_counts")
    op.drop_table("surgery_records")
    op.drop_table("surgery_safety_checks")
    op.drop_table("surgery_cases")
    op.drop_table("operating_rooms")
