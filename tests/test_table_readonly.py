"""所有业务表格默认只读，只有显式白名单列可编辑。"""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import his_client.ui  # noqa: F401  must import before taking QTableWidget from PySide6

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QAbstractItemView, QLineEdit


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


ROOT = Path(__file__).resolve().parents[1]


def test_qtablewidget_is_hardened_globally():
    import his_client.ui  # noqa: F401  triggers package-level replacement

    assert QtWidgets.QTableWidget is his_client.ui.ReadOnlyTable


def test_default_table_cannot_edit_even_after_show(qapp):
    import his_client.ui  # noqa: F401

    table = QTableWidget(1, 2)
    table.setItem(0, 0, QTableWidgetItem("不可编辑"))
    table.show()
    qapp.processEvents()
    assert table.editTriggers() == QAbstractItemView.NoEditTriggers
    assert table.edit(table.model().index(0, 0), QAbstractItemView.DoubleClicked, None) is False


def test_only_explicit_columns_are_editable(qapp):
    from his_client.ui.table_policy import ReadOnlyTable

    table = ReadOnlyTable(1, 2)
    table.setProperty("allow_cell_edit", True)
    table.setProperty("editable_columns", (1,))
    table.setItem(0, 0, QTableWidgetItem("ID"))
    table.setItem(0, 1, QTableWidgetItem("剂量"))
    table.setEditTriggers(
        QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
    )
    table.show()
    qapp.processEvents()
    assert table.edit(table.model().index(0, 0), QAbstractItemView.DoubleClicked, None) is False
    assert table.edit(table.model().index(0, 1), QAbstractItemView.DoubleClicked, None) is True


def test_no_ui_module_bypasses_readonly_factory():
    """UI 包内除策略文件外，不得直接配置表格编辑触发器。"""
    offenders = []
    for path in (ROOT / "his_client" / "ui").glob("*.py"):
        if path.name == "table_policy.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "setEditTriggers" in text:
            # 诊断编辑器只是显式关闭，允许；其他编辑入口必须走白名单属性
            if path.name == "diagnosis_editor.py":
                continue
            # 中药饮片表只允许“剂量”列，必须同时出现白名单属性
            if path.name == "doctor.py" and 'editable_columns", (2,)' in text:
                continue
            offenders.append(path.name)
    assert not offenders, offenders


def test_tcm_dose_whitelist_present():
    text = (ROOT / "his_client" / "ui" / "doctor.py").read_text(encoding="utf-8")
    assert 'setProperty("allow_cell_edit", True)' in text
    assert 'setProperty("editable_columns", (2,))' in text


def test_real_double_click_does_not_open_editor(qapp):
    import his_client.ui  # noqa: F401

    table = QTableWidget(1, 2)
    table.setItem(0, 0, QTableWidgetItem("不可编辑"))
    table.resize(320, 120)
    table.show()
    qapp.processEvents()
    rect = table.visualItemRect(table.item(0, 0))
    QTest.mouseDClick(table.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
    qapp.processEvents()
    assert table.state() != QAbstractItemView.EditingState
    assert not table.findChildren(QLineEdit)
    assert table.item(0, 0).text() == "不可编辑"
