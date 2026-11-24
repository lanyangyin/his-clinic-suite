"""PACS DICOM identifiers

Revision ID: 0114
Revises: 0113
"""
import sqlalchemy as sa
from alembic import op

revision = "0114"
down_revision = "0113"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.add_column(sa.Column("study_uid", sa.String(64), nullable=False, server_default=""))
        batch.add_column(sa.Column("series_uid", sa.String(64), nullable=False, server_default=""))
        batch.add_column(sa.Column("modality", sa.String(20), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.drop_column("modality")
        batch.drop_column("series_uid")
        batch.drop_column("study_uid")
