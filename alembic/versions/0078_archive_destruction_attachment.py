"""archive destruction attachment

Revision ID: 0078
Revises: 0077
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("archive_destruction_requests") as batch:
        batch.add_column(
            sa.Column(
                "attachment_path", sa.String(200), nullable=False, server_default=""
            )
        )
        batch.add_column(
            sa.Column(
                "attachment_name", sa.String(200), nullable=False, server_default=""
            )
        )


def downgrade():
    with op.batch_alter_table("archive_destruction_requests") as batch:
        batch.drop_column("attachment_name")
        batch.drop_column("attachment_path")
