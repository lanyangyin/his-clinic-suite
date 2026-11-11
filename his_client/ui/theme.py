"""统一现代化浅色工作站样式（白/浅蓝）。"""
MODERN_QSS = """
QWidget { color: #1e293b; font-family: "Microsoft YaHei"; font-size: 13px; }
QWidget#workstationRoot { background: #f4f8fd; }
QMainWindow, QDialog { background: #f4f8fd; }
QGroupBox {
    border: 1px solid #dbe7f3;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #1e3a5f;
    font-weight: 600;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #ffffff;
    border: 1px solid #cfdff0;
    border-radius: 6px;
    padding: 5px 8px;
    color: #1e293b;
    selection-background-color: #bfdbfe;
    selection-color: #0f172a;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #60a5fa;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #c7d8ea;
    border-radius: 6px;
    padding: 6px 12px;
    color: #1e3a5f;
}
QPushButton:hover { background: #eaf3ff; border-color: #60a5fa; }
QPushButton:pressed { background: #dbeafe; }
QPushButton:disabled { color: #94a3b8; background: #f8fafc; border-color: #e2e8f0; }
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f7fbff;
    gridline-color: #e6eef7;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
    border: 1px solid #dbe7f3;
    border-radius: 6px;
}
QTableWidget::item:selected { background: #dbeafe; color: #0f172a; }
QTableCornerButton::section { background: #eaf3ff; border: none; }
QHeaderView { background: #eaf3ff; }
QHeaderView::section {
    background: #eaf3ff;
    color: #1e3a5f;
    padding: 6px;
    border: none;
    border-right: 1px solid #dbe7f3;
    font-weight: 600;
}
QScrollBar:vertical { background: #f4f8fd; width: 10px; }
QScrollBar::handle:vertical { background: #b7cde3; border-radius: 5px; min-height: 24px; }
QSplitter::handle { background: #dbe7f3; width: 3px; }
QTabWidget::pane { border: 1px solid #dbe7f3; background: #ffffff; }
QStatusBar { color: #64748b; }
QToolTip { background: #ffffff; color: #1e293b; border: 1px solid #cfdff0; }
QCheckBox { color: #1e293b; }
QTextEdit { background: #ffffff; border: 1px solid #cfdff0; border-radius: 6px; color: #1e293b; }
"""


def apply_theme(widget) -> None:
    widget.setObjectName("workstationRoot")
    widget.setStyleSheet(MODERN_QSS)
