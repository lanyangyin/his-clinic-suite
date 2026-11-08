"""add doctor schedules and registration.schedule_id

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "doctor_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        # morning 上午 / afternoon 下午
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("booked", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "doctor_id", "schedule_date", "period", name="uq_schedules_doctor_date_period"
        ),
    )
    op.create_index("ix_doctor_schedules_id", "doctor_schedules", ["id"])
    op.create_index("ix_doctor_schedules_doctor_id", "doctor_schedules", ["doctor_id"])

    with op.batch_alter_table("registrations") as batch_op:
        batch_op.add_column(sa.Column("schedule_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_registrations_schedule_id", ["schedule_id"])
        batch_op.create_foreign_key(
            "fk_registrations_schedule_id", "doctor_schedules", ["schedule_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("registrations") as batch_op:
        batch_op.drop_constraint("fk_registrations_schedule_id", type_="foreignkey")
        batch_op.drop_index("ix_registrations_schedule_id")
        batch_op.drop_column("schedule_id")
    op.drop_index("ix_doctor_schedules_doctor_id", table_name="doctor_schedules")
    op.drop_index("ix_doctor_schedules_id", table_name="doctor_schedules")
    op.drop_table("doctor_schedules")
