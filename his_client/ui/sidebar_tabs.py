"""工作站主导航：横向页签，不旋转文字。"""
from PySide6.QtWidgets import QTabWidget


class SidebarTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setDocumentMode(True)
        self.setMovable(False)
        self.setUsesScrollButtons(True)
        self.setStyleSheet(
            """
            QTabWidget::pane { border: 1px solid #d7dce5; background: #ffffff; }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
                color: #334155;
                background: #eef2f7;
                border: 1px solid #d7dce5;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
                font-weight: bold;
                border-top: 3px solid #4f46e5;
            }
            QTabBar::tab:hover:!selected { background: #e2e8f0; }
            """
        )
