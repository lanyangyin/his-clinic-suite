"""public health platform receipt

Revision ID: 0110
Revises: 0109
"""
import sqlalchemy as sa
from alembic import op

revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("disease_reports") as batch:
        batch.add_column(sa.Column("receipt_no", sa.String(60), nullable=False, server_default=""))
        batch.add_column(sa.Column("submit_error", sa.String(300), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("disease_reports") as batch:
        batch.drop_column("submit_error")
        batch.drop_column("receipt_no")
