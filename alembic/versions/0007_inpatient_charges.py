"""add inpatient charges (执行医嘱自动计费)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inpatient_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False
        ),
        sa.Column(
            "execution_id",
            sa.Integer(),
            sa.ForeignKey("order_executions.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inpatient_charges_id", "inpatient_charges", ["id"])
    op.create_index(
        "ix_inpatient_charges_admission_id", "inpatient_charges", ["admission_id"]
    )
    op.create_index(
        "ix_inpatient_charges_execution_id", "inpatient_charges", ["execution_id"], unique=True
    )


def downgrade():
    op.drop_index("ix_inpatient_charges_execution_id", table_name="inpatient_charges")
    op.drop_index("ix_inpatient_charges_admission_id", table_name="inpatient_charges")
    op.drop_index("ix_inpatient_charges_id", table_name="inpatient_charges")
    op.drop_table("inpatient_charges")
