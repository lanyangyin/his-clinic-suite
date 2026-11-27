"""lab_items 增加 active，停用项目不再出现在医生开单目录。"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str = "0160"
down_revision: Union[str, None] = "0159"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    bind = op.get_bind()
    columns = {row["name"] for row in sa.inspect(bind).get_columns("lab_items")}
    if "active" not in columns:
        op.add_column("lab_items", sa.Column("active", sa.Boolean(), nullable=False, server_default="1"))
def downgrade() -> None:
    op.drop_column("lab_items", "active")
