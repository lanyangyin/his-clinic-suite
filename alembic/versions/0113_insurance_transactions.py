"""insurance transaction audit

Revision ID: 0113
Revises: 0112
"""
import sqlalchemy as sa
from alembic import op

revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "insurance_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="precheck"),
        sa.Column("drug_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("result", sa.String(20), nullable=False, server_default=""),
        sa.Column("message", sa.String(300), nullable=False, server_default=""),
        sa.Column("settlement_no", sa.String(60), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_insurance_transactions_encounter_id", "insurance_transactions", ["encounter_id"])


def downgrade():
    op.drop_index("ix_insurance_transactions_encounter_id", table_name="insurance_transactions")
    op.drop_table("insurance_transactions")
