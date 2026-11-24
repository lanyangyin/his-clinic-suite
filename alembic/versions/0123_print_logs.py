"""print logs

Revision ID: 0123
Revises: 0122
"""
import sqlalchemy as sa
from alembic import op
revision = "0123"
down_revision = "0122"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "print_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_print_logs_document_type", "print_logs", ["document_type"])

def downgrade():
    op.drop_index("ix_print_logs_document_type", table_name="print_logs")
    op.drop_table("print_logs")
