"""全局表格策略：业务表格默认只读，避免误双击改掉就诊/挂号数据。"""
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget


class _ReadOnlyTableFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QTableWidget):
            if obj.property("allow_cell_edit"):
                return False
            obj.setEditTriggers(QAbstractItemView.NoEditTriggers)
        return False


def install_readonly_table_policy(app) -> None:
    if getattr(app, "_readonly_table_filter", None) is None:
        app._readonly_table_filter = _ReadOnlyTableFilter(app)
        app.installEventFilter(app._readonly_table_filter)


def set_column_layout(
    table: QTableWidget,
    *,
    stretch: tuple[int, ...] = (),
    contents: tuple[int, ...] = (),
) -> None:
    """业务表格：关键列自适应拉伸，其余按内容宽度，避免最后一列吞掉空间。"""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for index in contents:
        if index < table.columnCount():
            header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
    for index in stretch:
        if index < table.columnCount():
            header.setSectionResizeMode(index, QHeaderView.Stretch)
