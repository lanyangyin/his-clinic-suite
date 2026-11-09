"""treatment follow-up results and photos

Revision ID: 0062
Revises: 0061
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("treatment_follow_ups") as batch:
        batch.add_column(sa.Column("result_note", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("healing_score", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("photo_path", sa.String(200), nullable=False, server_default=""))
        batch.add_column(sa.Column("completed_by", sa.String(50), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("treatment_follow_ups") as batch:
        batch.drop_column("completed_by")
        batch.drop_column("photo_path")
        batch.drop_column("healing_score")
        batch.drop_column("result_note")
