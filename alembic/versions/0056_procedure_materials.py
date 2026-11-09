"""procedure charges and material consumption

Revision ID: 0056
Revises: 0055
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("surgery_cases") as batch:
        batch.add_column(sa.Column("charge_item_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("price", sa.Float(), nullable=False, server_default="0"))

    op.create_table(
        "procedure_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="总库"),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_procedure_materials_id", "procedure_materials", ["id"])
    op.create_index("ix_procedure_materials_source", "procedure_materials", ["source_type", "source_id"])


def downgrade():
    op.drop_table("procedure_materials")
    with op.batch_alter_table("surgery_cases") as batch:
        batch.drop_column("price")
        batch.drop_column("charge_item_id")
