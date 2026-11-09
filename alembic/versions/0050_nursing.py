"""nursing infusion and order execution

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nursing_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False, server_default="infusion"),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("dosage", sa.String(50), nullable=False, server_default=""),
        sa.Column("route", sa.String(30), nullable=False, server_default=""),
        sa.Column("frequency", sa.String(20), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="routine"),
        sa.Column("seat_no", sa.String(20), nullable=False, server_default=""),
        sa.Column("rate_ml_h", sa.Float(), nullable=True),
        sa.Column("prepared_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("prepared_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("executed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("adverse_reaction", sa.String(200), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_type", "source_id", name="uq_nursing_source"),
    )
    op.create_index("ix_nursing_orders_id", "nursing_orders", ["id"])
    op.create_index("ix_nursing_orders_encounter_id", "nursing_orders", ["encounter_id"])

    op.create_table(
        "nursing_preparations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("nursing_orders.id"), nullable=False),
        sa.Column("solvent", sa.String(50), nullable=False, server_default=""),
        sa.Column("dose", sa.String(50), nullable=False, server_default=""),
        sa.Column("batch_no", sa.String(50), nullable=False, server_default=""),
        sa.Column("prepared_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("checked_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("prepared_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_nursing_preparations_id", "nursing_preparations", ["id"])
    op.create_index("ix_nursing_preparations_order_id", "nursing_preparations", ["order_id"])

    op.create_table(
        "nursing_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("nursing_orders.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("rate_ml_h", sa.Float(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("adverse_reaction", sa.String(200), nullable=True),
        sa.Column("nurse", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index("ix_nursing_observations_id", "nursing_observations", ["id"])
    op.create_index("ix_nursing_observations_order_id", "nursing_observations", ["order_id"])


def downgrade():
    op.drop_table("nursing_observations")
    op.drop_table("nursing_preparations")
    op.drop_table("nursing_orders")
