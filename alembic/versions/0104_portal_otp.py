"""portal login codes

Revision ID: 0104
Revises: 0103
"""
import sqlalchemy as sa
from alembic import op

revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_login_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("id_number", sa.String(30), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_portal_login_codes_id_number", "portal_login_codes", ["id_number"])


def downgrade():
    op.drop_index("ix_portal_login_codes_id_number", table_name="portal_login_codes")
    op.drop_table("portal_login_codes")
