"""工作站主导航：横向页签，不旋转文字；支持按需加载工作站。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget


class SidebarTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarTabs")
        self.setTabPosition(QTabWidget.North)
        self.setDocumentMode(True)
        self.setMovable(False)
        self.setUsesScrollButtons(True)
        self._lazy: dict[int, tuple[str, object]] = {}
        self._loading: set[int] = set()
        self.currentChanged.connect(self._ensure_tab)

    def add_lazy_tab(self, label: str, factory) -> int:
        """先放占位页，第一次切换到时才创建工作站。"""
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        hint = QLabel("正在加载工作站…")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#64748b;font-size:14px;")
        layout.addWidget(hint)
        index = self.addTab(placeholder, label)
        self._lazy[index] = (label, factory)
        return index

    def _ensure_tab(self, index: int) -> None:
        if index < 0 or index in self._loading:
            return
        entry = self._lazy.get(index)
        if entry is None:
            return
        label, factory = entry
        self._loading.add(index)
        try:
            widget = factory()
        except Exception as exc:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            hint = QLabel(f"工作站加载失败：{exc}")
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#b91c1c;font-size:13px;")
            layout.addWidget(hint)
        finally:
            self._loading.discard(index)
        self.blockSignals(True)
        try:
            self.removeTab(index)
            self.insertTab(index, widget, label)
            self.setCurrentIndex(index)
        finally:
            self.blockSignals(False)
        self._lazy.pop(index, None)

    def ensure_current(self) -> None:
        self._ensure_tab(self.currentIndex())
