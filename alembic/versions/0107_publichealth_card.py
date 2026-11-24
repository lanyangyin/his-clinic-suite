"""public health report card fields

Revision ID: 0107
Revises: 0106
"""
import sqlalchemy as sa
from alembic import op

revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("disease_reports") as batch:
        batch.add_column(sa.Column("report_type", sa.String(20), nullable=False, server_default="clinical"))
        batch.add_column(sa.Column("onset_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("diagnosis_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("report_unit", sa.String(100), nullable=False, server_default=""))
        batch.add_column(sa.Column("reporter_phone", sa.String(20), nullable=False, server_default=""))
        batch.add_column(sa.Column("is_correction", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch.add_column(sa.Column("correction_reason", sa.String(200), nullable=False, server_default=""))
        batch.add_column(sa.Column("is_death", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch.add_column(sa.Column("death_date", sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table("disease_reports") as batch:
        for column in ("death_date", "is_death", "correction_reason", "is_correction", "reporter_phone", "report_unit", "diagnosis_date", "onset_date", "report_type"):
            batch.drop_column(column)
