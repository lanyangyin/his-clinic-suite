"""dispense witness

Revision ID: 0102
Revises: 0101
"""
import sqlalchemy as sa
from alembic import op

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "dispensations",
        sa.Column("witness", sa.String(length=50), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_column("dispensations", "witness")
