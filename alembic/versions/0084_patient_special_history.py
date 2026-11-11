"""patient special history

Revision ID: 0084
Revises: 0083
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("patients") as batch:
        batch.add_column(
            sa.Column("special_history", sa.String(500), nullable=False, server_default="")
        )


def downgrade():
    with op.batch_alter_table("patients") as batch:
        batch.drop_column("special_history")
