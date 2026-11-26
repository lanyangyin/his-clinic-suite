"""national insurance production parameters

Revision ID: 0156
Revises: 0155
"""
from alembic import op
import sqlalchemy as sa
revision = "0156"
down_revision = "0155"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("institution_settings") as batch:
        batch.add_column(sa.Column("national_org_name", sa.String(100), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_infver", sa.String(10), nullable=False, server_default="V1.0"))
        batch.add_column(sa.Column("national_recer_sys_code", sa.String(20), nullable=False, server_default="HIS"))
        batch.add_column(sa.Column("national_mdtrtarea_code", sa.String(100), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_insuplc_code", sa.String(100), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_med_type", sa.String(10), nullable=False, server_default="11"))
        batch.add_column(sa.Column("national_sign_type", sa.String(10), nullable=False, server_default="SM2"))
        batch.add_column(sa.Column("national_security_mode", sa.String(20), nullable=False, server_default="plain"))
        batch.add_column(sa.Column("national_timeout", sa.Integer(), nullable=False, server_default="15"))
        batch.add_column(sa.Column("national_retry", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("national_dev_no", sa.String(100), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_dev_safe_info", sa.String(200), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_cert_path", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_cert_password", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_sm2_private_key", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_sm2_public_key", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("national_sm4_key", sa.String(500), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("institution_settings") as batch:
        for name in ("national_sm4_key", "national_sm2_public_key", "national_sm2_private_key",
                     "national_cert_password", "national_cert_path", "national_dev_safe_info",
                     "national_dev_no", "national_retry", "national_timeout", "national_security_mode",
                     "national_sign_type", "national_med_type", "national_insuplc_code",
                     "national_mdtrtarea_code", "national_recer_sys_code", "national_infver",
                     "national_org_name"):
            batch.drop_column(name)
