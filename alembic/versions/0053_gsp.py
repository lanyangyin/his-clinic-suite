"""GSP quality records

Revision ID: 0053
Revises: 0052
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gsp_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("acceptance_no", sa.String(30), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("supplier_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("delivery_no", sa.String(50), nullable=False, server_default=""),
        sa.Column("arrival_at", sa.DateTime(), nullable=False),
        sa.Column("transport_temp", sa.Float(), nullable=True),
        sa.Column("transport_ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("result", sa.String(20), nullable=False, server_default="qualified"),
        sa.Column("accepted_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_gsp_acceptances_id", "gsp_acceptances", ["id"])
    op.create_index("ix_gsp_acceptances_acceptance_no", "gsp_acceptances", ["acceptance_no"], unique=True)

    op.create_table(
        "gsp_acceptance_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("acceptance_id", sa.Integer(), sa.ForeignKey("gsp_acceptances.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="drug"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(60), nullable=False, server_default=""),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manufacturer", sa.String(100), nullable=False, server_default=""),
        sa.Column("approval_no", sa.String(60), nullable=False, server_default=""),
        sa.Column("result", sa.String(20), nullable=False, server_default="qualified"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_gsp_acceptance_items_id", "gsp_acceptance_items", ["id"])
    op.create_index("ix_gsp_acceptance_items_acceptance_id", "gsp_acceptance_items", ["acceptance_id"])

    op.create_table(
        "gsp_storage_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("log_type", sa.String(20), nullable=False, server_default="temperature"),
        sa.Column("area", sa.String(50), nullable=False, server_default="药房"),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("humidity", sa.Float(), nullable=True),
        sa.Column("equipment", sa.String(50), nullable=False, server_default=""),
        sa.Column("result", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_gsp_storage_logs_id", "gsp_storage_logs", ["id"])

    op.create_table(
        "gsp_adverse_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_name", sa.String(50), nullable=False),
        sa.Column("drug_name", sa.String(100), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("reaction", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="mild"),
        sa.Column("reported_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("reported_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="reported"),
    )
    op.create_index("ix_gsp_adverse_reactions_id", "gsp_adverse_reactions", ["id"])

    op.create_table(
        "gsp_recalls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recall_no", sa.String(30), nullable=False),
        sa.Column("drug_name", sa.String(100), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("level", sa.String(10), nullable=False, server_default="3"),
        sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
        sa.Column("initiated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_gsp_recalls_id", "gsp_recalls", ["id"])
    op.create_index("ix_gsp_recalls_recall_no", "gsp_recalls", ["recall_no"], unique=True)

    op.create_table(
        "gsp_personnel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default=""),
        sa.Column("certificate_no", sa.String(60), nullable=False, server_default=""),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("training_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_gsp_personnel_id", "gsp_personnel", ["id"])


def downgrade():
    op.drop_table("gsp_personnel")
    op.drop_table("gsp_recalls")
    op.drop_table("gsp_adverse_reactions")
    op.drop_table("gsp_storage_logs")
    op.drop_table("gsp_acceptance_items")
    op.drop_table("gsp_acceptances")
