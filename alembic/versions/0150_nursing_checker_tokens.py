"""nursing checker tokens

Revision ID: 0150
Revises: 0149
"""
import sqlalchemy as sa
from alembic import op
revision = "0150"
down_revision = "0149"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "nursing_checker_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_nursing_checker_tokens_token", "nursing_checker_tokens", ["token"], unique=True)

def downgrade():
    op.drop_index("ix_nursing_checker_tokens_token", table_name="nursing_checker_tokens")
    op.drop_table("nursing_checker_tokens")
