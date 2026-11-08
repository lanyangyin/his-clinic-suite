"""add inpatient orders and executions

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inpatient_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False
        ),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        # standing 长期医嘱 / stat 临时医嘱
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        # open 执行中 / stopped 已停止 / finished 已完成
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inpatient_orders_id", "inpatient_orders", ["id"])
    op.create_index("ix_inpatient_orders_admission_id", "inpatient_orders", ["admission_id"])

    op.create_table(
        "order_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id", sa.Integer(), sa.ForeignKey("inpatient_orders.id"), nullable=False
        ),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_order_executions_id", "order_executions", ["id"])
    op.create_index("ix_order_executions_order_id", "order_executions", ["order_id"])


def downgrade():
    op.drop_index("ix_order_executions_order_id", table_name="order_executions")
    op.drop_index("ix_order_executions_id", table_name="order_executions")
    op.drop_table("order_executions")
    op.drop_index("ix_inpatient_orders_admission_id", table_name="inpatient_orders")
    op.drop_index("ix_inpatient_orders_id", table_name="inpatient_orders")
    op.drop_table("inpatient_orders")
