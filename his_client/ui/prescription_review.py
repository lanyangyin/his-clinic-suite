"""药师处方审方工作站：待审处方、明细、通过/驳回。"""
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme

TYPE_LABELS = {
    "western": "西药/中成药",
    "tcm_herb": "中药饮片",
    "narcotic": "麻精",
    "special": "特殊",
}


class PrescriptionReviewWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.rows: list[dict] = []
        self.current: dict | None = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("处方审方（待药师审核）")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        refresh = QPushButton("刷新待审处方")
        refresh.clicked.connect(self._load)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(refresh)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["处方号", "患者", "类型", "医生", "品种数", "时间"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._select)
        splitter.addWidget(self.table)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.detail = QLabel("请选择一张待审处方")
        self.detail.setWordWrap(True)
        detail_layout.addWidget(self.detail)
        self.items = QTableWidget(0, 5)
        self.items.setHorizontalHeaderLabels(["药品", "规格", "数量", "用法", "金额"])
        self.items.horizontalHeader().setStretchLastSection(True)
        detail_layout.addWidget(self.items, 1)
        note_row = QHBoxLayout()
        self.note = QLineEdit()
        self.note.setPlaceholderText("审核意见 / 驳回原因（驳回必填）")
        self.approve = QPushButton("审核通过")
        self.reject = QPushButton("驳回")
        self.approve.clicked.connect(lambda: self._review(True))
        self.reject.clicked.connect(lambda: self._review(False))
        note_row.addWidget(self.note, 1)
        note_row.addWidget(self.approve)
        note_row.addWidget(self.reject)
        detail_layout.addLayout(note_row)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        detail_layout.addWidget(self.msg)
        splitter.addWidget(detail)
        splitter.setSizes([360, 280])
        layout.addWidget(splitter, 1)
        self._load()

    def _load(self) -> None:
        try:
            self.rows = self.api.list_pending_prescription_reviews()
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(self.rows))
        for row, item in enumerate(self.rows):
            values = [
                item.get("prescription_no") or "",
                f"{item.get('patient_name') or ''} {item.get('patient_no') or ''}",
                TYPE_LABELS.get(item.get("type"), item.get("type") or ""),
                item.get("doctor_name") or item.get("prescribed_by") or "",
                str(item.get("item_count") or 0),
                str(item.get("created_at") or "")[:16].replace("T", " "),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.msg.setText(f"待审处方 {len(self.rows)} 张")

    def _select(self, row: int, _col: int) -> None:
        if not 0 <= row < len(self.rows):
            return
        self.current = self.rows[row]
        try:
            lines = self.api.list_prescriptions(self.current["encounter_id"])
        except ApiError as e:
            self.msg.setText(f"加载明细失败（{e.status_code}）：{e.detail}")
            return
        lines = [
            line for line in lines if line.get("prescription_id") == self.current["id"]
        ]
        self.items.setRowCount(len(lines))
        total = 0.0
        for i, line in enumerate(lines):
            amount = float(line.get("quantity") or 0) * float(line.get("unit_price") or 0)
            total += amount
            values = [
                line.get("drug_name") or "",
                line.get("spec") or "—",
                str(line.get("quantity") or ""),
                " ".join(
                    str(x)
                    for x in (line.get("dosage"), line.get("frequency"), line.get("route"))
                    if x
                )
                or "—",
                f"{amount:.2f}",
            ]
            for col, value in enumerate(values):
                self.items.setItem(i, col, QTableWidgetItem(value))
        self.detail.setText(
            f"{self.current.get('prescription_no')}　患者："
            f"{self.current.get('patient_name')}　"
            f"医生：{self.current.get('doctor_name')}　"
            f"共 {len(lines)} 种，金额 {total:.2f} 元"
        )

    def _review(self, approve: bool) -> None:
        if not self.current:
            self.msg.setText("请先选择一张待审处方")
            return
        note = self.note.text().strip()
        if not approve and not note:
            self.msg.setText("驳回必须填写原因")
            return
        try:
            self.api.review_prescription(
                self.current["encounter_id"], self.current["id"], approve, note
            )
        except ApiError as e:
            self.msg.setText(f"处理失败（{e.status_code}）：{e.detail}")
            return
        self.current = None
        self.note.clear()
        self._load()
        self.msg.setText("已审核通过" if approve else "已驳回")
