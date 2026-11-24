"""notify retry backoff

Revision ID: 0130
Revises: 0129
"""
import sqlalchemy as sa
from alembic import op
revision = "0130"
down_revision = "0129"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("notification_outbox") as batch:
        batch.add_column(sa.Column("next_retry_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("notification_outbox") as batch:
        batch.drop_column("next_retry_at")
