"""全局表格策略：业务表格默认只读，避免误双击改掉就诊/挂号数据。"""
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget


class ReadOnlyTable(QTableWidget):
    """业务表格硬约束：默认禁止任何编辑，仅 allow_cell_edit + editable_columns 白名单放行。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        super().setEditTriggers(QAbstractItemView.NoEditTriggers)

    def _editable_columns(self) -> tuple[int, ...] | None:
        if not bool(self.property("allow_cell_edit")):
            return None
        columns = self.property("editable_columns")
        if columns is None:
            return ()
        return tuple(int(col) for col in columns)

    def setEditTriggers(self, triggers):
        if self._editable_columns() is None:
            super().setEditTriggers(QAbstractItemView.NoEditTriggers)
        else:
            super().setEditTriggers(triggers)

    def edit(self, index, trigger, event):
        columns = self._editable_columns()
        if columns is None or index.column() not in columns:
            return False
        return super().edit(index, trigger, event)


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
