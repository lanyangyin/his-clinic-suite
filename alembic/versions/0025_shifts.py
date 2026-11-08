"""add staff shifts (HRP)

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staff_shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False
        ),
        sa.Column("shift_date", sa.Date(), nullable=False),
        # morning 白班 / afternoon 中班 / night 夜班 / off 休息
        sa.Column("shift_type", sa.String(20), nullable=False),
        sa.UniqueConstraint("employee_id", "shift_date", name="uq_shift_employee_date"),
    )
    op.create_index("ix_staff_shifts_id", "staff_shifts", ["id"])
    op.create_index("ix_staff_shifts_employee_id", "staff_shifts", ["employee_id"])


def downgrade():
    op.drop_index("ix_staff_shifts_employee_id", table_name="staff_shifts")
    op.drop_index("ix_staff_shifts_id", table_name="staff_shifts")
    op.drop_table("staff_shifts")
