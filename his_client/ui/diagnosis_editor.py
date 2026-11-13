"""可排序的多诊断编辑器：第一行主诊断，其余其他诊断。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DiagnosisEditor(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[dict] = []
        self.edit_row = -1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["顺序", "类型", "编码", "诊断", "备注"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(130)
        self.table.setMaximumHeight(190)
        self.table.cellClicked.connect(self._select_row)
        layout.addWidget(self.table, 1)

        form = QHBoxLayout()
        self.code = QComboBox()
        self.code.addItem("编码（可选）", "")
        self.code.setMinimumWidth(180)
        self.code.currentIndexChanged.connect(self._code_changed)
        self.name = QLineEdit()
        self.name.setPlaceholderText("诊断名称，必填")
        self.note = QLineEdit()
        self.note.setPlaceholderText("备注（可选）")
        self.add_btn = QPushButton("添加/更新")
        self.add_btn.clicked.connect(self._commit)
        form.addWidget(self.code)
        form.addWidget(self.name, 1)
        form.addWidget(self.note, 1)
        form.addWidget(self.add_btn)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.remove_btn = QPushButton("删除选中")
        self.remove_btn.clicked.connect(self._remove)
        self.up_btn = QPushButton("上移")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = QPushButton("下移")
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.msg = QLabel("第一行为主诊断，按重要性从上到下排序")
        self.msg.setStyleSheet("color:#64748b")
        actions.addWidget(self.remove_btn)
        actions.addWidget(self.up_btn)
        actions.addWidget(self.down_btn)
        actions.addWidget(self.msg, 1)
        layout.addLayout(actions)

    def set_options(self, rows: list[dict]) -> None:
        current = self.code.currentData()
        self.code.blockSignals(True)
        self.code.clear()
        self.code.addItem("编码（可选）", "")
        for row in rows:
            self.code.addItem(f"{row['code']} {row['name']}", row["code"])
        index = self.code.findData(current or "")
        self.code.setCurrentIndex(max(0, index))
        self.code.blockSignals(False)

    def _code_changed(self, _index: int) -> None:
        code = self.code.currentData() or ""
        if not code:
            return
        text = self.code.currentText()
        if " " in text:
            self.name.setText(text.split(" ", 1)[1])
        self.note.setFocus()

    def set_items(self, rows: list[dict]) -> None:
        self.items = [
            {
                "diagnosis_code": row.get("diagnosis_code") or "",
                "diagnosis": row.get("diagnosis") or "",
                "note": row.get("note") or "",
            }
            for row in rows
            if (row.get("diagnosis") or "").strip()
        ]
        self.edit_row = -1
        self._render()

    def get_items(self) -> list[dict]:
        return [dict(item) for item in self.items]

    def set_editable(self, editable: bool) -> None:
        for widget in (
            self.code,
            self.name,
            self.note,
            self.add_btn,
            self.remove_btn,
            self.up_btn,
            self.down_btn,
        ):
            widget.setEnabled(editable)

    def _render(self) -> None:
        self.table.setRowCount(len(self.items))
        for index, item in enumerate(self.items):
            values = [
                str(index + 1),
                "主诊断" if index == 0 else "其他诊断",
                item.get("diagnosis_code") or "—",
                item.get("diagnosis") or "",
                item.get("note") or "",
            ]
            for col, value in enumerate(values):
                self.table.setItem(index, col, QTableWidgetItem(value))
        if self.items:
            self.table.selectRow(0)
            self.msg.setText(f"共 {len(self.items)} 条，第一行为主诊断")
        else:
            self.msg.setText("暂无诊断，第一行为主诊断")

    def _selected(self) -> int:
        row = self.table.currentRow()
        return row if 0 <= row < len(self.items) else -1

    def _select_row(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self.items)):
            return
        self.edit_row = row
        item = self.items[row]
        code_index = self.code.findData(item.get("diagnosis_code") or "")
        self.code.setCurrentIndex(max(0, code_index))
        self.name.setText(item.get("diagnosis") or "")
        self.note.setText(item.get("note") or "")

    def _commit(self) -> None:
        name = self.name.text().strip()
        if not name:
            self.msg.setText("诊断名称不能为空")
            return
        item = {
            "diagnosis_code": self.code.currentData() or "",
            "diagnosis": name,
            "note": self.note.text().strip(),
        }
        if self.edit_row >= 0 and self.edit_row < len(self.items):
            self.items[self.edit_row] = item
            target = self.edit_row
        else:
            self.items.append(item)
            target = len(self.items) - 1
        self.edit_row = -1
        self._render()
        self.table.selectRow(target)
        self.name.clear()
        self.note.clear()
        self.changed.emit()

    def _remove(self) -> None:
        row = self._selected()
        if row < 0:
            self.msg.setText("请先选择一条诊断")
            return
        del self.items[row]
        self.edit_row = -1
        self._render()
        self.changed.emit()

    def _move(self, delta: int) -> None:
        row = self._selected()
        target = row + delta
        if row < 0 or target < 0 or target >= len(self.items):
            return
        self.items[row], self.items[target] = self.items[target], self.items[row]
        self.edit_row = -1
        self._render()
        self.table.selectRow(target)
        self.changed.emit()


class DiagnosisDialog(QDialog):
    """多诊断编辑弹窗；第一行主诊断。"""

    def __init__(self, rows: list[dict], options: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("诊断（主诊断 + 其他诊断）")
        self.resize(720, 380)
        layout = QVBoxLayout(self)
        hint = QLabel("按重要性从上到下排序，第一行为主诊断。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.editor = DiagnosisEditor()
        self.editor.set_options(options)
        self.editor.set_items(rows)
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存诊断")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.editor.get_items():
            self.editor.msg.setText("至少填写一条诊断")
            return
        self.accept()

    def rows(self) -> list[dict]:
        return self.editor.get_items()
