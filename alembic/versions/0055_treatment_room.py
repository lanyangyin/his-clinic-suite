"""treatment room workflow

Revision ID: 0055
Revises: 0054
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "treatment_rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("location", sa.String(100), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_treatment_rooms_id", "treatment_rooms", ["id"])
    op.create_index("ix_treatment_rooms_code", "treatment_rooms", ["code"], unique=True)

    op.create_table(
        "treatment_room_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_no", sa.String(30), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("treatment_rooms.id"), nullable=True),
        sa.Column("treatment_order_id", sa.Integer(), nullable=True),
        sa.Column("procedure_name", sa.String(100), nullable=False),
        sa.Column("diagnosis", sa.String(200), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="waiting"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="routine"),
        sa.Column("charge_item_id", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("consent", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("anesthesia", sa.String(100), nullable=False, server_default=""),
        sa.Column("findings", sa.String(500), nullable=False, server_default=""),
        sa.Column("procedure_detail", sa.String(1000), nullable=False, server_default=""),
        sa.Column("sutures", sa.String(100), nullable=False, server_default=""),
        sa.Column("dressing", sa.String(200), nullable=False, server_default=""),
        sa.Column("materials", sa.String(200), nullable=False, server_default=""),
        sa.Column("complications", sa.String(200), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("requested_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_treatment_room_cases_id", "treatment_room_cases", ["id"])
    op.create_index("ix_treatment_room_cases_case_no", "treatment_room_cases", ["case_no"], unique=True)
    op.create_index("ix_treatment_room_cases_patient_id", "treatment_room_cases", ["patient_id"])


def downgrade():
    op.drop_table("treatment_room_cases")
    op.drop_table("treatment_rooms")
