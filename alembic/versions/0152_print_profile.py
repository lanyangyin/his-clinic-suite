"""print profile

Revision ID: 0152
Revises: 0151
"""
import sqlalchemy as sa
from alembic import op
revision = "0152"
down_revision = "0151"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "print_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("clinic_address", sa.String(200), nullable=False, server_default=""),
        sa.Column("clinic_phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("logo_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("theme_color", sa.String(20), nullable=False, server_default="#111111"),
        sa.Column("font_family", sa.String(200), nullable=False, server_default=""),
        sa.Column("paper_size", sa.String(10), nullable=False, server_default="A4"),
        sa.Column("margin_mm", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("header_note", sa.String(300), nullable=False, server_default=""),
        sa.Column("footer_note", sa.String(500), nullable=False, server_default=""),
        sa.Column("doctor_label", sa.String(30), nullable=False, server_default="医师"),
        sa.Column("reviewer_label", sa.String(30), nullable=False, server_default="审核药师"),
        sa.Column("dispenser_label", sa.String(30), nullable=False, server_default="调配药师"),
        sa.Column("checker_label", sa.String(30), nullable=False, server_default="核对、发药药师"),
        sa.Column("custom_css", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table("print_profile")
