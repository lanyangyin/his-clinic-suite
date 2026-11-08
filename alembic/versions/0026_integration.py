"""add integration logs

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("protocol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("message_type", sa.String(50), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_integration_logs_id", "integration_logs", ["id"])


def downgrade():
    op.drop_index("ix_integration_logs_id", table_name="integration_logs")
    op.drop_table("integration_logs")
