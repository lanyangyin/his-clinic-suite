"""add attendance records (HRP)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False
        ),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        # in 上班打卡 / out 下班打卡
        sa.Column("check_type", sa.String(10), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "employee_id", "attendance_date", "check_type", name="uq_attendance"
        ),
    )
    op.create_index("ix_attendance_records_id", "attendance_records", ["id"])
    op.create_index(
        "ix_attendance_records_employee_id", "attendance_records", ["employee_id"]
    )


def downgrade():
    op.drop_index("ix_attendance_records_employee_id", table_name="attendance_records")
    op.drop_index("ix_attendance_records_id", table_name="attendance_records")
    op.drop_table("attendance_records")
