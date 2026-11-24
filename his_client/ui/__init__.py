"""UI 包：导入时把 QTableWidget 全局替换为只读硬约束子类。

这样无论是正式客户端、登录后的工作站，还是独立演示脚本直接实例化页面，
所有业务表格都默认禁止双击/键盘编辑；仅显式设置 allow_cell_edit 与
editable_columns 的表格列可以编辑。
"""
from PySide6 import QtWidgets

from .table_policy import ReadOnlyTable

if QtWidgets.QTableWidget is not ReadOnlyTable:
    QtWidgets.QTableWidget = ReadOnlyTable

__all__ = ["ReadOnlyTable"]
