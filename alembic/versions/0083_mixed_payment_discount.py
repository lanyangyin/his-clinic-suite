"""mixed payment allocations + discount

Revision ID: 0083
Revises: 0082
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("discount_amount", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("discount_reason", sa.String(200), nullable=False, server_default=""))
        batch.add_column(sa.Column("discount_by", sa.String(50), nullable=False, server_default=""))
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("trade_no", sa.String(64), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_table("payment_allocations")
    with op.batch_alter_table("payments") as batch:
        batch.drop_column("discount_by")
        batch.drop_column("discount_reason")
        batch.drop_column("discount_amount")
