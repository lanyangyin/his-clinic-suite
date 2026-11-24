"""controlled drugs, narcotic rights, prescription insurance upload

Revision ID: 0095
Revises: 0094
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("drugs", sa.Column("controlled_level", sa.String(length=20), nullable=False, server_default=""))
    op.add_column("users", sa.Column("narcotic_right", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("prescriptions", sa.Column("insurance_upload_status", sa.String(length=20), nullable=False, server_default="not_ready"))
    op.add_column("prescriptions", sa.Column("insurance_uploaded_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("prescriptions", "insurance_uploaded_at")
    op.drop_column("prescriptions", "insurance_upload_status")
    op.drop_column("users", "narcotic_right")
    op.drop_column("drugs", "controlled_level")
