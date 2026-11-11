"""统一现代化工作站样式。"""
MODERN_QSS = """
QWidget { color: #e2e8f0; font-family: "Microsoft YaHei"; font-size: 13px; }
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    background: #111827;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #cbd5e1;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #0b1220;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 8px;
    color: #e2e8f0;
    selection-background-color: #4f46e5;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6366f1;
}
QPushButton {
    background: #1e293b;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e2e8f0;
}
QPushButton:hover { background: #334155; border-color: #6366f1; }
QPushButton:pressed { background: #4f46e5; }
QPushButton:disabled { color: #64748b; background: #111827; border-color: #1f2937; }
QTableWidget {
    background: #0b1220;
    alternate-background-color: #111827;
    gridline-color: #1f2937;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
    border: 1px solid #334155;
    border-radius: 6px;
}
QHeaderView::section {
    background: #1e293b;
    color: #cbd5e1;
    padding: 6px;
    border: none;
    border-right: 1px solid #334155;
}
QScrollBar:vertical { background: #0b1220; width: 10px; }
QScrollBar::handle:vertical { background: #475569; border-radius: 5px; min-height: 24px; }
QSplitter::handle { background: #1f2937; width: 3px; }
QStatusBar { color: #94a3b8; }
"""


def apply_theme(widget) -> None:
    widget.setStyleSheet(MODERN_QSS)
