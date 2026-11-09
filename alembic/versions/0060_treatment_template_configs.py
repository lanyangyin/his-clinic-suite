"""treatment template configs and kit flag

Revision ID: 0060
Revises: 0059
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("treatment_room_cases") as batch:
        batch.add_column(sa.Column("kit_applied", sa.Boolean(), nullable=False, server_default="0"))

    op.create_table(
        "treatment_template_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_code", sa.String(30), nullable=False, unique=True),
        sa.Column("charge_item_id", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("material_quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="总库"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_treatment_template_configs_id", "treatment_template_configs", ["id"])


def downgrade():
    op.drop_table("treatment_template_configs")
    with op.batch_alter_table("treatment_room_cases") as batch:
        batch.drop_column("kit_applied")
