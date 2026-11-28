"""治疗单增加开始执行时间/执行人。"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str = "0161"
down_revision: Union[str, None] = "0160"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    cols = {row["name"] for row in sa.inspect(bind).get_columns("treatment_orders")}
    if "started_by" not in cols:
        op.add_column("treatment_orders", sa.Column("started_by", sa.String(50), nullable=True))
    if "started_at" not in cols:
        op.add_column("treatment_orders", sa.Column("started_at", sa.DateTime(), nullable=True))

def downgrade() -> None:
    op.drop_column("treatment_orders", "started_at")
    op.drop_column("treatment_orders", "started_by")
