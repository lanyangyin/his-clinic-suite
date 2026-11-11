"""统一侧边栏页签：用于工作站主导航，避免所有页面都横排页签。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget


class SidebarTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabPosition(QTabWidget.West)
        self.setDocumentMode(True)
        self.setMovable(False)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.ElideNone)
        self.setStyleSheet(
            """
            QTabWidget::pane { border: 1px solid #d7dce5; background: #ffffff; }
            QTabBar::tab {
                min-width: 104px;
                padding: 14px 10px;
                margin: 2px 0;
                text-align: left;
                color: #334155;
                background: #eef2f7;
                border: 1px solid #d7dce5;
                border-right: none;
                border-top-left-radius: 5px;
                border-bottom-left-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
                font-weight: bold;
                border-left: 4px solid #4f46e5;
            }
            QTabBar::tab:hover:!selected { background: #e2e8f0; }
            """
        )
