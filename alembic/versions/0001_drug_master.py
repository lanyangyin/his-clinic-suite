"""drug master + prescription drug_id refactor

Revision ID: 0001
Revises:
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drugs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(50), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("base_price", sa.Float(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_drugs_id", "drugs", ["id"])

    # 存量处方行的药品名迁移为药品主数据（同名取最高价作为基准价）
    op.execute(
        "INSERT INTO drugs (name, base_price) "
        "SELECT drug_name, MAX(unit_price) FROM prescription_items GROUP BY drug_name"
    )

    with op.batch_alter_table("prescription_items") as batch_op:
        batch_op.add_column(sa.Column("drug_id", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE prescription_items SET drug_id = "
        "(SELECT id FROM drugs WHERE drugs.name = prescription_items.drug_name)"
    )

    with op.batch_alter_table("prescription_items") as batch_op:
        batch_op.alter_column(
            "drug_id", existing_type=sa.Integer(), nullable=False
        )
        batch_op.create_index("ix_prescription_items_drug_id", ["drug_id"])
        batch_op.create_foreign_key(
            "fk_prescription_items_drug_id", "drugs", ["drug_id"], ["id"]
        )
        batch_op.drop_column("drug_name")


def downgrade():
    with op.batch_alter_table("prescription_items") as batch_op:
        batch_op.add_column(sa.Column("drug_name", sa.String(100), nullable=True))

    op.execute(
        "UPDATE prescription_items SET drug_name = "
        "(SELECT name FROM drugs WHERE drugs.id = prescription_items.drug_id)"
    )

    with op.batch_alter_table("prescription_items") as batch_op:
        batch_op.drop_constraint("fk_prescription_items_drug_id", type_="foreignkey")
        batch_op.drop_index("ix_prescription_items_drug_id")
        batch_op.drop_column("drug_id")

    op.drop_index("ix_drugs_id", table_name="drugs")
    op.drop_table("drugs")
