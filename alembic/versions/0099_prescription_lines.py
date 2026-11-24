"""unified prescription lines

Revision ID: 0099
Revises: 0098
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prescription_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id"), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="drug"),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("herb_id", sa.Integer(), sa.ForeignKey("tcm_herbs.id"), nullable=True),
        sa.Column("source_item_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("spec", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("dosage", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("route", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_prescription_lines_prescription_id", "prescription_lines", ["prescription_id"])
    op.create_index("ix_prescription_lines_source_item_id", "prescription_lines", ["source_item_id"])

    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO prescription_lines
        (prescription_id, kind, drug_id, source_item_id, name, spec, quantity, unit,
         dosage, frequency, route, days, unit_price, amount, created_at)
        SELECT i.prescription_id, 'drug', i.drug_id, i.id, d.name, d.spec, i.quantity, d.unit,
               i.dosage, i.frequency, i.route, i.days, i.unit_price,
               ROUND(i.quantity * i.unit_price, 2), i.created_at
        FROM prescription_items i JOIN drugs d ON d.id = i.drug_id
        WHERE i.prescription_id IS NOT NULL
    """))
    conn.execute(sa.text("""
        INSERT INTO prescription_lines
        (prescription_id, kind, herb_id, source_item_id, name, spec, quantity, unit,
         days, unit_price, amount, created_at)
        SELECT p.prescription_id, 'herb', i.herb_id, i.id, h.name, h.spec, i.dose_g, h.unit,
               p.packs, h.price_per_g, ROUND(h.price_per_g * i.dose_g * p.packs, 2), p.created_at
        FROM tcm_prescription_items i
        JOIN tcm_prescriptions p ON p.id = i.prescription_id
        JOIN tcm_herbs h ON h.id = i.herb_id
        WHERE p.prescription_id IS NOT NULL
    """))


def downgrade():
    op.drop_index("ix_prescription_lines_source_item_id", table_name="prescription_lines")
    op.drop_index("ix_prescription_lines_prescription_id", table_name="prescription_lines")
    op.drop_table("prescription_lines")
