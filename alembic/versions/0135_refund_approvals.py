"""refund approvals

Revision ID: 0135
Revises: 0134
"""
import sqlalchemy as sa
from alembic import op
revision = "0135"
down_revision = "0134"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "refund_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("refund_no", sa.String(40), nullable=False, server_default=""),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("operator_role", sa.String(20), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refund_approvals_payment_id", "refund_approvals", ["payment_id"])

def downgrade():
    op.drop_index("ix_refund_approvals_payment_id", table_name="refund_approvals")
    op.drop_table("refund_approvals")
