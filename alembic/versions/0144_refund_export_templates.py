"""refund export templates

Revision ID: 0144
Revises: 0143
"""
import sqlalchemy as sa
from alembic import op
revision = "0144"
down_revision = "0143"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "refund_export_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("fields", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table("refund_export_templates")
