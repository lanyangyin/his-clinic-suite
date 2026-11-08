"""add payment created_at and finance closures

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

    op.create_table(
        "finance_closures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("close_date", sa.Date(), nullable=False),
        sa.Column("outpatient_paid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outpatient_paid_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("outpatient_refunded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outpatient_refunded_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("insurance_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("inpatient_charge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inpatient_charge_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(), nullable=False),
        sa.Column("closed_by", sa.String(50), nullable=False, server_default=""),
        sa.UniqueConstraint("close_date"),
    )
    op.create_index("ix_finance_closures_id", "finance_closures", ["id"])


def downgrade():
    op.drop_index("ix_finance_closures_id", table_name="finance_closures")
    op.drop_table("finance_closures")
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("created_at")
