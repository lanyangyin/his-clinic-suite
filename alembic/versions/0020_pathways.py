"""add clinical pathways, enrollments, variances

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clinical_pathways",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("diagnosis", sa.String(200), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_clinical_pathways_id", "clinical_pathways", ["id"])

    op.create_table(
        "pathway_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pathway_id", sa.Integer(), sa.ForeignKey("clinical_pathways.id"), nullable=False
        ),
        sa.Column(
            "admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False
        ),
        # active 进行中 / completed 已完成 / withdrawn 已退出
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("enrolled_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "pathway_id", "admission_id", name="uq_pathway_admission"
        ),
    )
    op.create_index("ix_pathway_enrollments_id", "pathway_enrollments", ["id"])
    op.create_index(
        "ix_pathway_enrollments_admission_id", "pathway_enrollments", ["admission_id"]
    )

    op.create_table(
        "pathway_variances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "enrollment_id",
            sa.Integer(),
            sa.ForeignKey("pathway_enrollments.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("noted_at", sa.DateTime(), nullable=False),
        sa.Column("noted_by", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index("ix_pathway_variances_id", "pathway_variances", ["id"])
    op.create_index(
        "ix_pathway_variances_enrollment_id", "pathway_variances", ["enrollment_id"]
    )


def downgrade():
    op.drop_index("ix_pathway_variances_enrollment_id", table_name="pathway_variances")
    op.drop_index("ix_pathway_variances_id", table_name="pathway_variances")
    op.drop_table("pathway_variances")
    op.drop_index("ix_pathway_enrollments_admission_id", table_name="pathway_enrollments")
    op.drop_index("ix_pathway_enrollments_id", table_name="pathway_enrollments")
    op.drop_table("pathway_enrollments")
    op.drop_index("ix_clinical_pathways_id", table_name="clinical_pathways")
    op.drop_table("clinical_pathways")
