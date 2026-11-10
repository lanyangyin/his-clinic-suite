"""treatment consent signature

Revision ID: 0074
Revises: 0073
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("treatment_room_cases") as batch:
        batch.add_column(
            sa.Column(
                "consent_version", sa.String(20), nullable=False, server_default="v1"
            )
        )
        batch.add_column(
            sa.Column("consent_signer", sa.String(50), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "consent_relation", sa.String(20), nullable=False, server_default=""
            )
        )
        batch.add_column(
            sa.Column(
                "consent_signature_path",
                sa.String(200),
                nullable=False,
                server_default="",
            )
        )
        batch.add_column(sa.Column("consent_signed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("treatment_room_cases") as batch:
        batch.drop_column("consent_signed_at")
        batch.drop_column("consent_signature_path")
        batch.drop_column("consent_relation")
        batch.drop_column("consent_signer")
        batch.drop_column("consent_version")
