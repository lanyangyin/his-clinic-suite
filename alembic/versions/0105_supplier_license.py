"""supplier license/status

Revision ID: 0105
Revises: 0104
"""
import sqlalchemy as sa
from alembic import op

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("suppliers") as batch:
        batch.add_column(sa.Column("license_no", sa.String(60), nullable=False, server_default=""))
        batch.add_column(sa.Column("license_expiry", sa.Date(), nullable=True))
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="active"))
        batch.add_column(sa.Column("first_business_approved", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch.add_column(sa.Column("blacklist_reason", sa.String(200), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("suppliers") as batch:
        batch.drop_column("blacklist_reason")
        batch.drop_column("first_business_approved")
        batch.drop_column("status")
        batch.drop_column("license_expiry")
        batch.drop_column("license_no")
