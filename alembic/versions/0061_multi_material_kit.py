"""multi-material treatment kits and material returns

Revision ID: 0061
Revises: 0060
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "treatment_template_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(), sa.ForeignKey("treatment_template_configs.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_items.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="总库"),
    )
    op.create_index("ix_treatment_template_materials_id", "treatment_template_materials", ["id"])
    op.create_index("ix_treatment_template_materials_config_id", "treatment_template_materials", ["config_id"])

    # 把旧版单耗材配置迁入多耗材表
    op.execute(
        """
        INSERT INTO treatment_template_materials (config_id, material_id, quantity, warehouse)
        SELECT id, material_id, material_quantity, warehouse
        FROM treatment_template_configs
        WHERE material_id IS NOT NULL
        """
    )

    with op.batch_alter_table("procedure_materials") as batch:
        batch.add_column(sa.Column("returned_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("procedure_materials") as batch:
        batch.drop_column("returned_at")
    op.drop_table("treatment_template_materials")
