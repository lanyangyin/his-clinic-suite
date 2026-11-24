"""integration config

Revision ID: 0100
Revises: 0099
"""
import sqlalchemy as sa
from alembic import op

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_configs",
        sa.Column("key", sa.String(length=60), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("integration_configs")
