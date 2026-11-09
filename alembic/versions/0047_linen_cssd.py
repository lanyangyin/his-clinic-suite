"""linen laundry and CSSD instrument sterilization

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "linen_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_no", sa.String(30), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="bedding"),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False, server_default="件"),
        sa.Column("source_department", sa.String(50), nullable=False, server_default=""),
        sa.Column("soil_level", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("wash_method", sa.String(20), nullable=False, server_default="thermal"),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("detergent", sa.String(100), nullable=False, server_default=""),
        sa.Column("washed_at", sa.DateTime(), nullable=False),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_linen_batches_id", "linen_batches", ["id"])
    op.create_index("ix_linen_batches_batch_no", "linen_batches", ["batch_no"], unique=True)

    op.create_table(
        "linen_distributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("linen_batches.id"), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("distributed_at", sa.DateTime(), nullable=False),
        sa.Column("distributed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_linen_distributions_id", "linen_distributions", ["id"])
    op.create_index("ix_linen_distributions_batch_id", "linen_distributions", ["batch_id"])

    op.create_table(
        "curtain_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("room", sa.String(50), nullable=False, server_default=""),
        sa.Column("curtain_no", sa.String(50), nullable=False),
        sa.Column("event", sa.String(20), nullable=False),
        sa.Column("event_at", sa.DateTime(), nullable=False),
        sa.Column("method", sa.String(50), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("next_due", sa.Date(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_curtain_records_id", "curtain_records", ["id"])

    op.create_table(
        "instrument_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("department", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_instrument_sets_id", "instrument_sets", ["id"])
    op.create_index("ix_instrument_sets_code", "instrument_sets", ["code"], unique=True)

    op.create_table(
        "sterilization_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_no", sa.String(30), nullable=False),
        sa.Column("sterilizer", sa.String(50), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="steam"),
        sa.Column("cycle", sa.String(30), nullable=False, server_default=""),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("chemical_indicator", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("biological_indicator", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("release_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("released_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sterilization_batches_id", "sterilization_batches", ["id"])
    op.create_index("ix_sterilization_batches_batch_no", "sterilization_batches", ["batch_no"], unique=True)

    op.create_table(
        "instrument_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_code", sa.String(50), nullable=False),
        sa.Column("set_id", sa.Integer(), sa.ForeignKey("instrument_sets.id"), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("sterilization_batches.id"), nullable=False),
        sa.Column("sterilized_at", sa.DateTime(), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="sterilized"),
        sa.Column("location", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_instrument_packages_id", "instrument_packages", ["id"])
    op.create_index("ix_instrument_packages_package_code", "instrument_packages", ["package_code"], unique=True)

    op.create_table(
        "package_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("instrument_packages.id"), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.Column("used_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_package_usages_id", "package_usages", ["id"])
    op.create_index("ix_package_usages_package_id", "package_usages", ["package_id"])


def downgrade():
    op.drop_table("package_usages")
    op.drop_table("instrument_packages")
    op.drop_table("sterilization_batches")
    op.drop_table("instrument_sets")
    op.drop_table("curtain_records")
    op.drop_table("linen_distributions")
    op.drop_table("linen_batches")
