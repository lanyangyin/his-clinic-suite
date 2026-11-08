"""add inpatient tables: wards, beds, admissions

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_wards_id", "wards", ["id"])

    op.create_table(
        "beds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ward_id", sa.Integer(), sa.ForeignKey("wards.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="empty"),
        sa.UniqueConstraint("ward_id", "code", name="uq_beds_ward_code"),
    )
    op.create_index("ix_beds_id", "beds", ["id"])
    op.create_index("ix_beds_ward_id", "beds", ["ward_id"])

    op.create_table(
        "admissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("bed_id", sa.Integer(), sa.ForeignKey("beds.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in"),
        sa.Column("admitted_at", sa.DateTime(), nullable=False),
        sa.Column("discharged_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_admissions_id", "admissions", ["id"])
    op.create_index("ix_admissions_patient_id", "admissions", ["patient_id"])
    op.create_index("ix_admissions_bed_id", "admissions", ["bed_id"])


def downgrade():
    op.drop_index("ix_admissions_bed_id", table_name="admissions")
    op.drop_index("ix_admissions_patient_id", table_name="admissions")
    op.drop_index("ix_admissions_id", table_name="admissions")
    op.drop_table("admissions")
    op.drop_index("ix_beds_ward_id", table_name="beds")
    op.drop_index("ix_beds_id", table_name="beds")
    op.drop_table("beds")
    op.drop_index("ix_wards_id", table_name="wards")
    op.drop_table("wards")
