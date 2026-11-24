"""imaging report templates

Revision ID: 0109
Revises: 0108
"""
import sqlalchemy as sa
from alembic import op

revision = "0109"
down_revision = "0108"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "imaging_report_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("body_part", sa.String(50), nullable=False, server_default=""),
        sa.Column("findings", sa.String(1000), nullable=False, server_default=""),
        sa.Column("impression", sa.String(500), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("imaging_report_templates")
