"""partial refund by charge item

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("encounter_charges") as batch:
        batch.add_column(
            sa.Column(
                "refunded_quantity",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.alter_column(
            "status",
            existing_type=sa.String(10),
            type_=sa.String(30),
            existing_nullable=False,
        )

    with op.batch_alter_table("payments") as batch:
        batch.add_column(
            sa.Column(
                "refunded_amount", sa.Float(), nullable=False, server_default="0"
            )
        )
        batch.add_column(
            sa.Column(
                "refunded_insurance_amount",
                sa.Float(),
                nullable=False,
                server_default="0",
            )
        )

    op.create_table(
        "charge_refunds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column(
            "charge_id",
            sa.Integer(),
            sa.ForeignKey("encounter_charges.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("insurance_amount", sa.Float(), nullable=False),
        sa.Column("self_pay_amount", sa.Float(), nullable=False),
        sa.Column("refund_no", sa.String(40), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("channel_trade_no", sa.String(64), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_charge_refunds_id", "charge_refunds", ["id"])
    op.create_index("ix_charge_refunds_payment_id", "charge_refunds", ["payment_id"])


def downgrade():
    op.drop_index("ix_charge_refunds_payment_id", table_name="charge_refunds")
    op.drop_index("ix_charge_refunds_id", table_name="charge_refunds")
    op.drop_table("charge_refunds")
    with op.batch_alter_table("payments") as batch:
        batch.drop_column("refunded_insurance_amount")
        batch.drop_column("refunded_amount")
    with op.batch_alter_table("encounter_charges") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.String(30),
            type_=sa.String(10),
            existing_nullable=False,
        )
        batch.drop_column("refunded_quantity")
