"""ICD-10 diagnosis code and common diagnosis seed

Revision ID: 0071
Revises: 0070
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None

DIAGNOSES = [
    ("J06.9", "急性上呼吸道感染"),
    ("J18.9", "肺炎"),
    ("J45.9", "支气管哮喘"),
    ("I10", "高血压"),
    ("E11.9", "2型糖尿病"),
    ("E78.5", "高脂血症"),
    ("K29.7", "胃炎"),
    ("K52.9", "腹泻"),
    ("N39.0", "尿路感染"),
    ("M54.5", "腰痛"),
    ("R50.9", "发热"),
    ("R05", "咳嗽"),
    ("S01.9", "头部裂伤"),
    ("S61.9", "手部开放性伤口"),
    ("S00.9", "头部浅表损伤"),
    ("L03.9", "蜂窝织炎"),
    ("H10.9", "结膜炎"),
    ("G43.9", "偏头痛"),
    ("F41.9", "焦虑状态"),
    ("T78.4", "过敏反应"),
]


def upgrade():
    with op.batch_alter_table("encounters") as batch:
        batch.add_column(
            sa.Column(
                "diagnosis_code", sa.String(20), nullable=False, server_default=""
            )
        )

    op.bulk_insert(
        sa.table(
            "dict_entries",
            sa.column("dict_type", sa.String),
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("sort_order", sa.Integer),
            sa.column("active", sa.Boolean),
        ),
        [
            {
                "dict_type": "diagnosis_icd10",
                "code": code,
                "name": name,
                "sort_order": index,
                "active": True,
            }
            for index, (code, name) in enumerate(DIAGNOSES)
        ],
    )


def downgrade():
    op.execute("DELETE FROM dict_entries WHERE dict_type = 'diagnosis_icd10'")
    with op.batch_alter_table("encounters") as batch:
        batch.drop_column("diagnosis_code")
