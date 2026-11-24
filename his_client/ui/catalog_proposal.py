"""新药品 / 新治疗项目建议与部门审核工作站。"""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.theme import apply_theme

STATUS_LABELS = {
    "pending_pharmacy": "待药事审核",
    "pending_warehouse": "待库房审核",
    "pending_director": "待院长审批",
    "approved": "已批准并建档",
    "rejected": "已驳回",
}
KIND_LABELS = {"drug": "药品", "treatment": "治疗项目"}


class CatalogProposalDialog(QDialog):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.kind = kind
        self.setWindowTitle("建议新增药品" if kind == "drug" else "建议新增治疗项目")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.spec = QLineEdit()
        self.unit = QLineEdit()
        self.price = QLineEdit()
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("临床需要/适应症/为什么现有目录不够")
        form.addRow("名称*", self.name)
        form.addRow("规格", self.spec)
        form.addRow("单位", self.unit)
        form.addRow("建议价格", self.price)
        form.addRow("理由*", self.reason)
        layout.addLayout(form)
        hint = QLabel(
            "药品：药事审核 → 库房审核 → 建档；治疗项目：院长审批 → 建档。"
            "医生不能直接修改目录。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b;")
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("提交建议")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.name.text().strip() or not self.reason.text().strip():
            return
        self.accept()

    def payload(self) -> dict:
        try:
            price = float(self.price.text().strip() or 0)
        except ValueError:
            price = 0.0
        return {
            "kind": self.kind,
            "name": self.name.text().strip(),
            "spec": self.spec.text().strip(),
            "unit": self.unit.text().strip(),
            "price": max(0.0, price),
            "reason": self.reason.text().strip(),
        }


class CatalogReviewWidget(QWidget):
    """药事/库房/院长共用审核页，按阶段决定按钮和可用接口。"""

    def __init__(self, api: ApiClient, stage: str, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.stage = stage
        self.rows: list[dict] = []
        title = {
            "pharmacy": "药事审核",
            "warehouse": "库房审核",
            "treatment": "治疗项目审批",
        }[stage]
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        heading = QLabel(title)
        heading.setStyleSheet("font-size:16px;font-weight:bold")
        refresh = QPushButton("刷新待审核")
        refresh.clicked.connect(self._load)
        top.addWidget(heading)
        top.addStretch(1)
        top.addWidget(refresh)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "类型", "名称", "规格", "单位", "建议价", "申请人"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._select)
        layout.addWidget(self.table, 1)

        self.detail = QLabel("请选择一条建议")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.note = QLineEdit()
        self.note.setPlaceholderText("审核意见/驳回原因")
        layout.addWidget(self.note)
        actions = QHBoxLayout()
        self.approve = QPushButton(
            "通过药事审核"
            if stage == "pharmacy"
            else "通过并建立药品" if stage == "warehouse" else "批准并建立治疗项目"
        )
        self.reject = QPushButton("驳回")
        self.approve.clicked.connect(lambda: self._review(True))
        self.reject.clicked.connect(lambda: self._review(False))
        actions.addWidget(self.approve)
        actions.addWidget(self.reject)
        self.msg = QLabel("")
        actions.addWidget(self.msg, 1)
        layout.addLayout(actions)
        self._load()

    def _load(self) -> None:
        try:
            self.rows = self.api.list_catalog_proposals()
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(self.rows))
        for row, item in enumerate(self.rows):
            values = [
                str(item["id"]),
                KIND_LABELS.get(item["kind"], item["kind"]),
                item["name"],
                item.get("spec") or "—",
                item.get("unit") or "—",
                f"{item.get('price', 0):.2f}",
                item.get("requested_by") or "",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.msg.setText(f"待审核 {len(self.rows)} 条")

    def _select(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.rows):
            item = self.rows[row]
            self.detail.setText(
                f"{KIND_LABELS.get(item['kind'], item['kind'])}：{item['name']}\n"
                f"规格：{item.get('spec') or '—'}　单位：{item.get('unit') or '—'}　"
                f"建议价：{item.get('price', 0):.2f}\n"
                f"申请人：{item.get('requested_by') or '—'}\n"
                f"理由：{item.get('reason') or '—'}"
            )

    def _review(self, approve: bool) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.rows):
            self.msg.setText("请先选择一条建议")
            return
        item = self.rows[row]
        try:
            result = self.api.review_catalog_proposal(
                item["id"], approve, self.note.text().strip()
            )
        except ApiError as e:
            self.msg.setText(f"处理失败（{e.status_code}）：{e.detail}")
            return
        self._load()
        self.msg.setText(f"已处理：{STATUS_LABELS.get(result['status'], result['status'])}")
