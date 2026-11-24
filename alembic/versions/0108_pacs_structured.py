"""PACS structured report

Revision ID: 0108
Revises: 0107
"""
import sqlalchemy as sa
from alembic import op

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.add_column(sa.Column("findings", sa.String(1000), nullable=False, server_default=""))
        batch.add_column(sa.Column("impression", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("template_name", sa.String(100), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.drop_column("template_name")
        batch.drop_column("impression")
        batch.drop_column("findings")
