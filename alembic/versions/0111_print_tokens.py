"""print one-time tokens

Revision ID: 0111
Revises: 0110
"""
import sqlalchemy as sa
from alembic import op

revision = "0111"
down_revision = "0110"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "print_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", sa.String(30), nullable=False, server_default=""),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_print_tokens_token_hash", "print_tokens", ["token_hash"], unique=True)


def downgrade():
    op.drop_index("ix_print_tokens_token_hash", table_name="print_tokens")
    op.drop_table("print_tokens")
