"""treatment room templates

Revision ID: 0058
Revises: 0057
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("treatment_room_cases") as batch:
        batch.add_column(sa.Column("template_code", sa.String(30), nullable=False, server_default=""))
        batch.add_column(sa.Column("template_data", sa.String(2000), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("treatment_room_cases") as batch:
        batch.drop_column("template_data")
        batch.drop_column("template_code")
