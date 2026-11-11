"""工作站主导航：横向页签，不旋转文字。"""
from PySide6.QtWidgets import QTabWidget

from his_client.ui.theme import colors


class SidebarTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setDocumentMode(True)
        self.setMovable(False)
        self.setUsesScrollButtons(True)
        c = colors()
        self.setStyleSheet(
            f"""
            QTabWidget {{ background: {c['bg']}; }}
            QTabWidget::pane {{ border: 1px solid {c['border']}; background: {c['surface']}; }}
            QTabBar {{ background: {c['bg']}; }}
            QTabBar::tab {{
                padding: 8px 16px; margin-right: 2px;
                color: {c['text']};
                background: {c['header']};
                border: 1px solid {c['border']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background: {c['surface']};
                color: {c['title']};
                font-weight: bold;
                border-top: 3px solid #6366f1;
            }}
            QTabBar::tab:hover:!selected {{ background: {c['selected']}; }}
            """
        )
