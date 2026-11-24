"""统一审批待办视图（只读聚合，具体处理仍在各业务工作站）。"""
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme

ACTION_BIZ = {
    "prescription_review": "prescription",
    "purchase_request": "purchase_request",
    "archive_destruction": "archive_destruction",
    "salary_request": "salary_request",
}

STATUS_LABELS = {
    "pending_review": "待审方",
    "pending": "待审批",
    "submitted": "待审批",
    "pending_pharmacy": "待药师审核",
    "pending_warehouse": "待库房审核",
    "pending_director": "待院长审核",
}

KIND_LABELS = {
    "prescription_review": "处方审方",
    "catalog_proposal": "目录建议",
    "warehouse_outbound": "库房出库",
    "purchase_request": "采购申请",
    "archive_destruction": "病案销毁",
    "treatment_proposal": "治疗项目",
    "salary_request": "薪资申请",
}


class ApprovalInboxWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.rows: list[dict] = []
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("审批待办")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(refresh)
        layout.addLayout(top)
        hint = QLabel("可在此直接处理处方/采购/病案/薪资；目录建议和出库仍回原工作站。")
        hint.setStyleSheet("color:#64748b;")
        layout.addWidget(hint)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["类型", "单据", "申请人", "状态", "时间"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        action_row = QHBoxLayout()
        self.note = QLineEdit()
        self.note.setPlaceholderText("审批意见 / 驳回原因（驳回必填）")
        approve = QPushButton("通过选中")
        reject = QPushButton("驳回选中")
        approve.clicked.connect(lambda: self._act(True))
        reject.clicked.connect(lambda: self._act(False))
        action_row.addWidget(self.note, 1)
        action_row.addWidget(approve)
        action_row.addWidget(reject)
        layout.addLayout(action_row)
        self.msg = QLabel("")
        layout.addWidget(self.msg)
        self._load()

    def _load(self) -> None:
        try:
            self.rows = self.api.list_approval_inbox()
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(self.rows))
        for row, item in enumerate(self.rows):
            values = [
                KIND_LABELS.get(item.get("kind"), item.get("kind") or ""),
                item.get("title") or "",
                item.get("applicant") or "",
                STATUS_LABELS.get(item.get("status"), item.get("status") or ""),
                str(item.get("created_at") or "")[:16].replace("T", " "),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.msg.setText(f"待办 {len(self.rows)} 项")


    def _act(self, approve: bool) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.rows):
            self.msg.setText("请先选择一条待办")
            return
        item = self.rows[row]
        biz_type = ACTION_BIZ.get(item.get("kind"))
        if not biz_type:
            self.msg.setText("该类待办请到对应业务工作站处理")
            return
        note = self.note.text().strip()
        if not approve and not note:
            self.msg.setText("驳回必须填写原因")
            return
        try:
            result = self.api.act_approval(
                {
                    "biz_type": biz_type,
                    "biz_id": item["id"],
                    "action": "approve" if approve else "reject",
                    "note": note,
                }
            )
        except ApiError as e:
            self.msg.setText(f"处理失败（{e.status_code}）：{e.detail}")
            return
        state = result.get("result") or ""
        self.note.clear()
        self._load()
        self.msg.setText(
            {
                "approved": "已通过",
                "rejected": "已驳回",
                "pending": "已通过当前步骤，等待下一级",
                "transferred": "已转交",
            }.get(state, f"已处理：{state}")
        )
