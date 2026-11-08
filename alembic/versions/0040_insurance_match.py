"""drug insurance matching

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drugs") as batch:
        batch.add_column(
            sa.Column("insurance_category", sa.String(10), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "insurance_match_status",
                sa.String(20),
                nullable=False,
                server_default="unmatched",
            )
        )
    with op.batch_alter_table("prescription_items") as batch:
        batch.add_column(
            sa.Column("insurance_category", sa.String(10), nullable=False, server_default="")
        )


def downgrade():
    with op.batch_alter_table("prescription_items") as batch:
        batch.drop_column("insurance_category")
    with op.batch_alter_table("drugs") as batch:
        batch.drop_column("insurance_match_status")
        batch.drop_column("insurance_category")
