"""insurance material catalog + material insurance_code

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "insurance_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(30), nullable=False, server_default=""),
        sa.Column("spec", sa.String(80), nullable=False, server_default=""),
        sa.Column("model", sa.String(80), nullable=False, server_default=""),
        sa.Column("manufacturer", sa.String(100), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("material_type", sa.String(20), nullable=False, server_default="耗材"),
        sa.Column("registration_no", sa.String(60), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_insurance_materials_id", "insurance_materials", ["id"])
    op.create_index("ix_insurance_materials_code", "insurance_materials", ["code"])
    op.create_index("ix_insurance_materials_name", "insurance_materials", ["name"])

    with op.batch_alter_table("material_items") as batch:
        batch.add_column(
            sa.Column(
                "insurance_code", sa.String(60), nullable=False, server_default=""
            )
        )


def downgrade():
    with op.batch_alter_table("material_items") as batch:
        batch.drop_column("insurance_code")
    op.drop_index("ix_insurance_materials_name", table_name="insurance_materials")
    op.drop_index("ix_insurance_materials_code", table_name="insurance_materials")
    op.drop_index("ix_insurance_materials_id", table_name="insurance_materials")
    op.drop_table("insurance_materials")
