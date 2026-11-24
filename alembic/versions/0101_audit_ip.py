"""audit ip fields

Revision ID: 0101
Revises: 0100
"""
import sqlalchemy as sa
from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audit_logs", sa.Column("ip", sa.String(length=45), nullable=False, server_default=""))
    op.add_column("patient_access_logs", sa.Column("ip", sa.String(length=45), nullable=False, server_default=""))


def downgrade():
    op.drop_column("patient_access_logs", "ip")
    op.drop_column("audit_logs", "ip")
