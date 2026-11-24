"""notification templates

Revision ID: 0136
Revises: 0135
"""
import sqlalchemy as sa
from alembic import op
revision = "0136"
down_revision = "0135"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("title", sa.String(120), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("channel", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notification_templates_code", "notification_templates", ["code"], unique=True)

def downgrade():
    op.drop_index("ix_notification_templates_code", table_name="notification_templates")
    op.drop_table("notification_templates")
