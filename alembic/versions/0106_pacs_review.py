"""PACS report reviewer

Revision ID: 0106
Revises: 0105
"""
import sqlalchemy as sa
from alembic import op

revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.add_column(sa.Column("reported_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("reviewed_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("review_note", sa.String(200), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.drop_column("review_note")
        batch.drop_column("reviewed_at")
        batch.drop_column("reviewed_by")
        batch.drop_column("reported_by")
