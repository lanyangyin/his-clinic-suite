"""add dictionary entries (master data)

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dict_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dict_type", sa.String(50), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("dict_type", "code", name="uq_dict_type_code"),
    )
    op.create_index("ix_dict_entries_id", "dict_entries", ["id"])
    op.create_index("ix_dict_entries_dict_type", "dict_entries", ["dict_type"])


def downgrade():
    op.drop_index("ix_dict_entries_dict_type", table_name="dict_entries")
    op.drop_index("ix_dict_entries_id", table_name="dict_entries")
    op.drop_table("dict_entries")
