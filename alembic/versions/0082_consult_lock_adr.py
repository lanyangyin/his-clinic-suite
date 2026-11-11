"""doctor current encounter + adverse reactions

Revision ID: 0082
Revises: 0081
Create Date: 2026-11-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("doctors") as batch:
        batch.add_column(
            sa.Column("current_encounter_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_doctors_current_encounter",
            "encounters",
            ["current_encounter_id"],
            ["id"],
        )
    op.create_table(
        "adverse_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"),
            nullable=False, index=True,
        ),
        sa.Column("drug_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("reaction", sa.String(500), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="moderate"),
        sa.Column("action_taken", sa.String(500), nullable=False, server_default=""),
        sa.Column("reported_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("adverse_reactions")
    with op.batch_alter_table("doctors") as batch:
        batch.drop_column("current_encounter_id")
