"""通用分页条：可调每页条数、上一页/下一页、页码跳转。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QWidget


class PaginationBar(QWidget):
    pageChanged = Signal(int)
    pageSizeChanged = Signal(int)

    def __init__(self, page_sizes=(20, 50, 100, 200), parent=None):
        super().__init__(parent)
        self._total = 0
        self._page = 1
        self._page_size = page_sizes[0]
        self._page_sizes = tuple(page_sizes)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        self.total_label = QLabel("共 0 条")
        self.size_combo = QComboBox()
        for size in self._page_sizes:
            self.size_combo.addItem(f"{size} 条/页", size)
        self.size_combo.currentIndexChanged.connect(self._on_size)
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(lambda: self.set_page(self._page - 1, emit=True))
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.page_spin.setPrefix("第 ")
        self.page_spin.setSuffix(" 页")
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.valueChanged.connect(lambda value: self.set_page(value, emit=True))
        self.pages_label = QLabel("/ 1 页")
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(lambda: self.set_page(self._page + 1, emit=True))
        layout.addWidget(self.total_label)
        layout.addStretch(1)
        layout.addWidget(QLabel("每页"))
        layout.addWidget(self.size_combo)
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.page_spin)
        layout.addWidget(self.pages_label)
        layout.addWidget(self.next_btn)
        self._refresh()

    def page_size(self) -> int:
        return self._page_size

    def page(self) -> int:
        return self._page

    def page_count(self) -> int:
        return max(1, (self._total + self._page_size - 1) // self._page_size)

    def set_total(self, total: int) -> None:
        self._total = max(0, int(total))
        self._page = min(max(1, self._page), self.page_count())
        self._refresh()

    def set_page(self, page: int, emit: bool = False) -> None:
        page = min(max(1, int(page)), self.page_count())
        if page == self._page:
            self._refresh()
            return
        self._page = page
        self._refresh()
        if emit:
            self.pageChanged.emit(self._page)

    def _on_size(self, _index: int) -> None:
        self._page_size = int(self.size_combo.currentData() or 20)
        self._page = 1
        self._refresh()
        self.pageSizeChanged.emit(self._page_size)

    def _refresh(self) -> None:
        self.total_label.setText(f"共 {self._total} 条")
        self.page_spin.blockSignals(True)
        self.page_spin.setRange(1, self.page_count())
        self.page_spin.setValue(self._page)
        self.page_spin.blockSignals(False)
        self.pages_label.setText(f"/ {self.page_count()} 页")
        self.prev_btn.setEnabled(self._page > 1)
        self.next_btn.setEnabled(self._page < self.page_count())
