"""跟随系统的浅色/深色主题。HIS_THEME=light|dark 可强制覆盖。"""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

LIGHT_QSS = """
QWidget { color: #1e293b; font-family: "Microsoft YaHei"; font-size: 13px; }
QWidget#workstationRoot { background: #f4f8fd; }
QMainWindow, QDialog { background: #f4f8fd; }
QGroupBox {
    border: 1px solid #dbe7f3; border-radius: 8px; margin-top: 12px;
    padding: 10px 8px 8px 8px; background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
    color: #1e3a5f; font-weight: 600;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #ffffff; border: 1px solid #cfdff0; border-radius: 6px;
    padding: 5px 8px; color: #1e293b;
    selection-background-color: #bfdbfe; selection-color: #0f172a;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #60a5fa;
}
QPushButton {
    background: #ffffff; border: 1px solid #c7d8ea; border-radius: 6px;
    padding: 6px 12px; color: #1e3a5f;
}
QPushButton:hover { background: #eaf3ff; border-color: #60a5fa; }
QPushButton:pressed { background: #dbeafe; }
QPushButton:disabled { color: #94a3b8; background: #f8fafc; border-color: #e2e8f0; }
QTableWidget {
    background: #ffffff; alternate-background-color: #f7fbff;
    gridline-color: #e6eef7; selection-background-color: #dbeafe;
    selection-color: #0f172a; border: 1px solid #dbe7f3; border-radius: 6px;
}
QTableWidget::item:selected { background: #dbeafe; color: #0f172a; }
QTableCornerButton::section { background: #eaf3ff; border: none; }
QHeaderView { background: #eaf3ff; }
QHeaderView::section {
    background: #eaf3ff; color: #1e3a5f; padding: 6px; border: none;
    border-right: 1px solid #dbe7f3; font-weight: 600;
}
QScrollBar:vertical { background: #f4f8fd; width: 10px; }
QScrollBar::handle:vertical { background: #b7cde3; border-radius: 5px; min-height: 24px; }
QSplitter::handle { background: #dbe7f3; width: 3px; }
QTabWidget::pane { border: 1px solid #dbe7f3; background: #ffffff; }
QStatusBar { color: #64748b; }
QToolTip { background: #ffffff; color: #1e293b; border: 1px solid #cfdff0; }
QCheckBox, QRadioButton { color: #1e293b; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid #b7cde3;
    border-radius: 3px; background: #ffffff;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #2563eb; border: 1px solid #2563eb;
}
QComboBox QAbstractItemView {
    background: #ffffff; color: #1e293b; border: 1px solid #cfdff0;
    selection-background-color: #dbeafe; selection-color: #0f172a;
}
QMenu { background: #ffffff; color: #1e293b; border: 1px solid #cfdff0; }
QMenu::item:selected { background: #dbeafe; color: #0f172a; }
QTextEdit { background: #ffffff; border: 1px solid #cfdff0; border-radius: 6px; color: #1e293b; }
"""

DARK_QSS = """
QWidget { color: #e2e8f0; font-family: "Microsoft YaHei"; font-size: 13px; }
QWidget#workstationRoot { background: #0f172a; }
QMainWindow, QDialog { background: #0f172a; }
QGroupBox {
    border: 1px solid #334155; border-radius: 8px; margin-top: 12px;
    padding: 10px 8px 8px 8px; background: #111827;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
    color: #cbd5e1; font-weight: 600;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #0b1220; border: 1px solid #334155; border-radius: 6px;
    padding: 5px 8px; color: #e2e8f0;
    selection-background-color: #4f46e5; selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6366f1;
}
QPushButton {
    background: #1e293b; border: 1px solid #475569; border-radius: 6px;
    padding: 6px 12px; color: #e2e8f0;
}
QPushButton:hover { background: #334155; border-color: #6366f1; }
QPushButton:pressed { background: #4f46e5; }
QPushButton:disabled { color: #64748b; background: #111827; border-color: #1f2937; }
QTableWidget {
    background: #0b1220; alternate-background-color: #111827;
    gridline-color: #1f2937; selection-background-color: #4f46e5;
    selection-color: #ffffff; border: 1px solid #334155; border-radius: 6px;
}
QTableWidget::item:selected { background: #4f46e5; color: #ffffff; }
QTableCornerButton::section { background: #1e293b; border: none; }
QHeaderView { background: #1e293b; }
QHeaderView::section {
    background: #1e293b; color: #cbd5e1; padding: 6px; border: none;
    border-right: 1px solid #334155; font-weight: 600;
}
QScrollBar:vertical { background: #0b1220; width: 10px; }
QScrollBar::handle:vertical { background: #475569; border-radius: 5px; min-height: 24px; }
QSplitter::handle { background: #1f2937; width: 3px; }
QTabWidget::pane { border: 1px solid #334155; background: #111827; }
QStatusBar { color: #94a3b8; }
QToolTip { background: #1e293b; color: #e2e8f0; border: 1px solid #475569; }
QCheckBox, QRadioButton { color: #e2e8f0; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid #475569;
    border-radius: 3px; background: #0b1220;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #4f46e5; border: 1px solid #6366f1;
}
QComboBox QAbstractItemView {
    background: #111827; color: #e2e8f0; border: 1px solid #334155;
    selection-background-color: #4f46e5; selection-color: #ffffff;
}
QMenu { background: #111827; color: #e2e8f0; border: 1px solid #334155; }
QMenu::item:selected { background: #4f46e5; color: #ffffff; }
QTextEdit { background: #0b1220; border: 1px solid #334155; border-radius: 6px; color: #e2e8f0; }
"""


def is_dark() -> bool:
    forced = os.environ.get("HIS_THEME", "").strip().lower()
    if forced in ("dark", "light"):
        return forced == "dark"
    app = QGuiApplication.instance()
    if app is not None:
        try:
            if app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
                return True
        except (AttributeError, TypeError):
            pass
        if app.palette().color(QPalette.Window).lightness() < 128:
            return True
    return False


def colors() -> dict:
    if is_dark():
        return {
            "bg": "#0f172a", "surface": "#111827", "card": "#1e293b",
            "border": "#334155", "text": "#e2e8f0", "title": "#f8fafc",
            "muted": "#94a3b8", "input": "#0b1220", "header": "#1e293b",
            "selected": "#4f46e5", "danger": "#f87171", "warning": "#fbbf24",
            "success": "#4ade80",
        }
    return {
        "bg": "#f4f8fd", "surface": "#ffffff", "card": "#ffffff",
        "border": "#dbe7f3", "text": "#1e293b", "title": "#0f172a",
        "muted": "#64748b", "input": "#ffffff", "header": "#eaf3ff",
        "selected": "#dbeafe", "danger": "#dc2626", "warning": "#b45309",
        "success": "#15803d",
    }


def apply_theme(widget) -> None:
    widget.setObjectName("workstationRoot")
    dark = is_dark()
    c = colors()
    palette = widget.palette()
    palette.setColor(QPalette.Window, QColor(c["bg"]))
    palette.setColor(QPalette.WindowText, QColor(c["text"]))
    palette.setColor(QPalette.Base, QColor(c["input"]))
    palette.setColor(QPalette.AlternateBase, QColor(c["surface"]))
    palette.setColor(QPalette.Text, QColor(c["text"]))
    palette.setColor(QPalette.Button, QColor(c["surface"]))
    palette.setColor(QPalette.ButtonText, QColor(c["text"]))
    palette.setColor(QPalette.Highlight, QColor(c["selected"]))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff" if dark else "#0f172a"))
    palette.setColor(QPalette.ToolTipBase, QColor(c["surface"]))
    palette.setColor(QPalette.ToolTipText, QColor(c["text"]))
    palette.setColor(QPalette.PlaceholderText, QColor(c["muted"]))
    widget.setPalette(palette)
    widget.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)
