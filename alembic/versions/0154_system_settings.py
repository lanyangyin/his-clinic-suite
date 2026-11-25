"""system settings

Revision ID: 0154
Revises: 0153
"""
import sqlalchemy as sa
from alembic import op
revision = "0154"
down_revision = "0153"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table("system_settings")
