"""drug ingredient + interaction rules

Revision ID: 0080
Revises: 0079
Create Date: 2026-11-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drugs") as batch:
        batch.add_column(
            sa.Column("ingredient", sa.String(100), nullable=False, server_default="")
        )
    op.create_table(
        "drug_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_a_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("drug_b_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="block"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.UniqueConstraint("drug_a_id", "drug_b_id", name="uq_drug_interaction_pair"),
    )


def downgrade():
    op.drop_table("drug_interactions")
    with op.batch_alter_table("drugs") as batch:
        batch.drop_column("ingredient")
