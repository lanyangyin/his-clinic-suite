"""站内通知中心：审批待办/结果、超时升级。"""
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme


class NotificationWidget(QWidget):
    def __init__(self, api: ApiClient, can_dispatch: bool = False, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.rows: list[dict] = []
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("通知中心")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load)
        top.addWidget(title)
        top.addStretch(1)
        if can_dispatch:
            retry = QPushButton("重试失败")
            retry.clicked.connect(self._retry)
            dispatch = QPushButton("派发待发送")
            dispatch.clicked.connect(self._dispatch)
            top.addWidget(retry)
            top.addWidget(dispatch)
        top.addWidget(refresh)
        layout.addLayout(top)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["时间", "渠道", "标题", "状态"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._read)
        layout.addWidget(self.table, 1)
        self.msg = QLabel("")
        layout.addWidget(self.msg)
        self._load()

    def _load(self) -> None:
        try:
            self.rows = self.api.list_notifications()
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            values = [
                str(row.get("created_at") or "")[:16].replace("T", " "),
                row.get("channel") or "",
                row.get("title") or "",
                row.get("status") or "",
            ]
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        unread = sum(1 for row in self.rows if row.get("status") == "pending")
        self.msg.setText(f"共 {len(self.rows)} 条，待读 {unread} 条")

    def _read(self, row: int, _col: int) -> None:
        if not 0 <= row < len(self.rows):
            return
        item = self.rows[row]
        if item.get("status") == "pending":
            try:
                self.api.read_notification(item["id"])
            except ApiError as e:
                self.msg.setText(f"标记已读失败：{e.detail}")
                return
            self._load()

    def _retry(self) -> None:
        try:
            result = self.api.retry_notifications()
        except ApiError as e:
            self.msg.setText(f"重试失败：{e.detail}")
            return
        self.msg.setText(f"已重置 {result.get('retried', 0)} 条失败通知")
        self._load()

    def _dispatch(self) -> None:
        try:
            result = self.api.dispatch_notifications()
        except ApiError as e:
            self.msg.setText(f"派发失败：{e.detail}")
            return
        self.msg.setText(
            f"已处理 {result.get('processed', 0)} 条，成功 {result.get('sent', 0)}，失败 {result.get('failed', 0)}"
        )
        self._load()
