"""add appointments, campuses/rooms, invoice_no, sms

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("address", sa.String(200), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_campuses_id", "campuses", ["id"])

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campus_id", sa.Integer(), sa.ForeignKey("campuses.id"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("campus_id", "code", name="uq_room_campus_code"),
    )
    op.create_index("ix_rooms_id", "rooms", ["id"])

    with op.batch_alter_table("doctor_schedules") as batch:
        batch.add_column(sa.Column("room_id", sa.Integer(), nullable=True))

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column(
            "schedule_id", sa.Integer(), sa.ForeignKey("doctor_schedules.id"), nullable=False
        ),
        sa.Column(
            "registration_id", sa.Integer(), sa.ForeignKey("registrations.id"), nullable=True
        ),
        # booked 已预约 / checked_in 已取号 / no_show 爽约 / cancelled 已取消
        sa.Column("status", sa.String(20), nullable=False, server_default="booked"),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_appointments_id", "appointments", ["id"])
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])

    with op.batch_alter_table("payments") as batch:
        # SQLite batch 模式不允许匿名唯一约束：先加列，再用命名唯一索引
        batch.add_column(sa.Column("invoice_no", sa.String(30), nullable=True))
    op.create_index(
        "ix_payments_invoice_no", "payments", ["invoice_no"], unique=True
    )

    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("content", sa.String(200), nullable=False),
        sa.Column("template", sa.String(30), nullable=False, server_default=""),
        # sent 已发送（Mock）/ failed 失败
        sa.Column("status", sa.String(10), nullable=False, server_default="sent"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sms_messages_id", "sms_messages", ["id"])


def downgrade():
    op.drop_index("ix_sms_messages_id", table_name="sms_messages")
    op.drop_table("sms_messages")
    op.drop_index("ix_payments_invoice_no", table_name="payments")
    with op.batch_alter_table("payments") as batch:
        batch.drop_column("invoice_no")
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.drop_index("ix_appointments_id", table_name="appointments")
    op.drop_table("appointments")
    with op.batch_alter_table("doctor_schedules") as batch:
        batch.drop_column("room_id")
    op.drop_index("ix_rooms_id", table_name="rooms")
    op.drop_table("rooms")
    op.drop_index("ix_campuses_id", table_name="campuses")
    op.drop_table("campuses")
