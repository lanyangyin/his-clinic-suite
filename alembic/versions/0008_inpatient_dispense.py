"""add inpatient dispense requests (摆药/退药)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inpatient_dispense_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False
        ),
        sa.Column(
            "order_id", sa.Integer(), sa.ForeignKey("inpatient_orders.id"), nullable=False
        ),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        # pending 待摆药 / dispensed 已发药 / returned 已退药
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("dispensed_at", sa.DateTime(), nullable=True),
        sa.Column("returned_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_inpatient_dispense_requests_id", "inpatient_dispense_requests", ["id"])
    op.create_index(
        "ix_inpatient_dispense_requests_admission_id",
        "inpatient_dispense_requests",
        ["admission_id"],
    )
    op.create_index(
        "ix_inpatient_dispense_requests_order_id",
        "inpatient_dispense_requests",
        ["order_id"],
    )


def downgrade():
    op.drop_index(
        "ix_inpatient_dispense_requests_order_id", table_name="inpatient_dispense_requests"
    )
    op.drop_index(
        "ix_inpatient_dispense_requests_admission_id", table_name="inpatient_dispense_requests"
    )
    op.drop_index("ix_inpatient_dispense_requests_id", table_name="inpatient_dispense_requests")
    op.drop_table("inpatient_dispense_requests")
