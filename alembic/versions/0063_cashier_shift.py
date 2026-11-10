"""cashier shifts and daily close

Revision ID: 0063
Revises: 0062
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("created_by", sa.String(50), nullable=False, server_default=""))

    op.create_table(
        "cashier_shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shift_no", sa.String(30), nullable=False, unique=True),
        sa.Column("cashier", sa.String(50), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("opening_float", sa.Float(), nullable=False, server_default="0"),
        sa.Column("counted_cash", sa.Float(), nullable=True),
        sa.Column("expected_cash", sa.Float(), nullable=True),
        sa.Column("difference", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_cashier_shifts_id", "cashier_shifts", ["id"])
    op.create_index("ix_cashier_shifts_cashier", "cashier_shifts", ["cashier"])


def downgrade():
    op.drop_table("cashier_shifts")
    with op.batch_alter_table("payments") as batch:
        batch.drop_column("created_by")
