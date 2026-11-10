"""pharmacy pickup code and signature

Revision ID: 0068
Revises: 0067
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dispensations") as batch:
        batch.add_column(sa.Column("receiver_name", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("receiver_relation", sa.String(20), nullable=False, server_default="本人"))
        batch.add_column(sa.Column("signature_path", sa.String(200), nullable=False, server_default=""))
        batch.add_column(sa.Column("signed_at", sa.DateTime(), nullable=True))

    op.create_table(
        "pharmacy_pickup_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False, unique=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pharmacy_pickup_codes_id", "pharmacy_pickup_codes", ["id"])
    op.create_index("ix_pharmacy_pickup_codes_encounter_id", "pharmacy_pickup_codes", ["encounter_id"])
    op.create_index("ix_pharmacy_pickup_codes_code", "pharmacy_pickup_codes", ["code"])


def downgrade():
    op.drop_table("pharmacy_pickup_codes")
    with op.batch_alter_table("dispensations") as batch:
        batch.drop_column("signed_at")
        batch.drop_column("signature_path")
        batch.drop_column("receiver_relation")
        batch.drop_column("receiver_name")
