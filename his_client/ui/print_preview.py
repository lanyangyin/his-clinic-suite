"""内嵌打印预览：用 QTextBrowser 渲染服务端 /print/... 页面。

不依赖 QtWebEngine，避免打包环境缺少 QtWebEngineProcess 时客户端闪退。
"""
import re
from pathlib import Path
import requests

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QPageSize
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from his_client.ui.theme import apply_theme


class PrintPreviewDialog(QDialog):
    def __init__(self, url: str, title: str = "打印预览", parent=None, auth=None):
        super().__init__(parent)
        self.auth = auth
        apply_theme(self)
        self.url = url
        self.setWindowTitle(title)
        self.resize(900, 760)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.status = QLabel("正在加载打印模板…")
        bar.addWidget(self.status, 1)
        self.print_btn = QPushButton("打印")
        self.print_btn.clicked.connect(self._print)
        self.pdf_btn = QPushButton("导出 PDF")
        self.pdf_btn.clicked.connect(self._export_pdf)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load)
        close = QPushButton("关闭")
        close.clicked.connect(self.reject)
        for button in (self.print_btn, self.pdf_btn, refresh, close):
            bar.addWidget(button)
        layout.addLayout(bar)

        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(False)
        layout.addWidget(self.browser, 1)
        self._load()

    def _load(self) -> None:
        self.status.setText("正在加载打印模板…")
        try:
            response = requests.get(self.url, timeout=10, auth=self.auth)
            response.raise_for_status()
            html = response.text
            # 预览窗口自己提供打印按钮，移除模板里的按钮
            html = re.sub(r"<button\b.*?</button>", "", html, flags=re.I | re.S)
            self.browser.document().setBaseUrl(QUrl(self.url))
            self.browser.setHtml(html)
            self.status.setText("预览已加载")
        except Exception as e:  # noqa: BLE001
            self.browser.setPlainText(f"加载失败：{e}")
            self.status.setText("模板加载失败，请检查服务端是否运行")

    def _new_printer(self) -> QPrinter:
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A5))
        printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)
        return printer

    def _print(self) -> None:
        printer = self._new_printer()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.browser.document().print_(printer)
            self.status.setText("已发送到打印机")
        except Exception as e:  # noqa: BLE001
            self.status.setText(f"打印失败：{e}")

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出打印预览 PDF", "打印预览.pdf", "PDF 文件 (*.pdf)"
        )
        if not path:
            return
        printer = self._new_printer()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        try:
            self.browser.document().print_(printer)
            self.status.setText(f"已导出：{Path(path).name}")
        except Exception as e:  # noqa: BLE001
            self.status.setText(f"导出失败：{e}")


def open_print_preview(parent, url: str, title: str = "打印预览") -> None:
    api = getattr(parent, "api", None)
    auth = getattr(getattr(api, "session", None), "auth", None)
    dialog = PrintPreviewDialog(url, title, parent, auth=auth)
    dialog.exec()
