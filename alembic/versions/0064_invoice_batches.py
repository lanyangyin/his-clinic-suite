"""invoice batches and payment batch link

Revision ID: 0064
Revises: 0063
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("invoice_batch_id", sa.Integer(), nullable=True))

    op.create_table(
        "invoice_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prefix", sa.String(20), nullable=False, server_default="INV"),
        sa.Column("start_no", sa.Integer(), nullable=False),
        sa.Column("end_no", sa.Integer(), nullable=False),
        sa.Column("next_no", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.String(50), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_invoice_batches_id", "invoice_batches", ["id"])


def downgrade():
    op.drop_table("invoice_batches")
    with op.batch_alter_table("payments") as batch:
        batch.drop_column("invoice_batch_id")
