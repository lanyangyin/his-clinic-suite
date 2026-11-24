"""registration timestamps

Revision ID: 0133
Revises: 0132
"""
import sqlalchemy as sa
from alembic import op
revision = "0133"
down_revision = "0132"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("registrations") as batch:
        batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch.add_column(sa.Column("created_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("registrations") as batch:
        batch.drop_column("cancelled_at")
        batch.drop_column("created_by")
        batch.drop_column("created_at")
