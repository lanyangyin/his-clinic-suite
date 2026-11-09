"""病案档案工作站：建档、归档上架、借阅/归还、复印、封存/启封、销毁。"""
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError

STATUS = {
    "draft": "已建档",
    "archived": "已归档",
    "borrowed": "已借出",
    "sealed": "已封存",
    "destroyed": "已销毁",
}
TYPES = {"outpatient": "门诊", "inpatient": "住院", "emergency": "急诊"}


class ArchiveWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.rows: list[dict] = []
        self.current: dict | None = None
        tabs = QTabWidget()
        tabs.addTab(self._build_record_tab(), "病案建档 / 归档")
        tabs.addTab(self._build_borrow_tab(), "借阅 / 复印")
        tabs.addTab(self._build_seal_tab(), "封存 / 销毁")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def _build_record_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        create_box = QGroupBox("病案建档")
        form = QFormLayout(create_box)
        self.patient_id = QSpinBox()
        self.patient_id.setRange(1, 10_000_000)
        self.encounter_id = QSpinBox()
        self.encounter_id.setRange(0, 10_000_000)
        self.encounter_id.setSpecialValueText("不关联就诊")
        self.record_type = QComboBox()
        for value, label in TYPES.items():
            self.record_type.addItem(label, value)
        self.note = QLineEdit()
        create = QPushButton("建档")
        create.clicked.connect(self._create)
        form.addRow("患者 ID", self.patient_id)
        form.addRow("就诊 ID（可选）", self.encounter_id)
        form.addRow("类型", self.record_type)
        form.addRow("备注", self.note)
        form.addRow("", create)
        layout.addWidget(create_box)

        top = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItem("全部", None)
        for value, label in STATUS.items():
            self.status_filter.addItem(label, value)
        refresh = QPushButton("刷新病案列表")
        refresh.clicked.connect(self._refresh)
        top.addWidget(QLabel("状态"))
        top.addWidget(self.status_filter)
        top.addWidget(refresh)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["病案号", "患者", "类型", "页数", "状态", "库位", "建档时间"]
        )
        self.table.cellClicked.connect(self._select)
        layout.addWidget(self.table, 1)

        archive_box = QGroupBox("归档上架")
        archive_form = QFormLayout(archive_box)
        self.location = QLineEdit()
        self.location.setPlaceholderText("如 A区-03架-02层")
        self.pages = QSpinBox()
        self.pages.setRange(1, 10000)
        self.completeness = QComboBox()
        self.completeness.addItem("完整", "complete")
        self.completeness.addItem("不完整", "incomplete")
        archive_btn = QPushButton("归档选中病案")
        archive_btn.clicked.connect(self._archive)
        archive_form.addRow("库位", self.location)
        archive_form.addRow("页数", self.pages)
        archive_form.addRow("完整性", self.completeness)
        archive_form.addRow("", archive_btn)
        layout.addWidget(archive_box)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        layout.addWidget(self.msg)
        return page

    def _build_borrow_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        refresh = QPushButton("刷新可借阅病案")
        refresh.clicked.connect(self._refresh_borrow)
        layout.addWidget(refresh)
        self.borrow_table = QTableWidget(0, 6)
        self.borrow_table.setHorizontalHeaderLabels(
            ["病案号", "患者", "状态", "库位", "借阅人", "应还日期"]
        )
        self.borrow_table.cellClicked.connect(self._select_borrow)
        layout.addWidget(self.borrow_table, 1)

        borrow_box = QGroupBox("借阅")
        borrow_form = QFormLayout(borrow_box)
        self.borrower = QLineEdit()
        self.department = QLineEdit()
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(7)
        borrow_btn = QPushButton("借出")
        borrow_btn.clicked.connect(self._borrow)
        return_btn = QPushButton("归还")
        return_btn.clicked.connect(self._return)
        borrow_form.addRow("借阅人", self.borrower)
        borrow_form.addRow("科室", self.department)
        borrow_form.addRow("借期(天)", self.days)
        borrow_form.addRow(borrow_btn, return_btn)
        layout.addWidget(borrow_box)

        copy_box = QGroupBox("复印登记")
        copy_form = QFormLayout(copy_box)
        self.applicant = QLineEdit()
        self.relationship = QLineEdit("本人")
        self.copies = QSpinBox()
        self.copies.setRange(1, 100)
        self.copy_contents = QLineEdit()
        self.copy_contents.setPlaceholderText("如 出院记录、检验报告")
        copy_btn = QPushButton("登记复印")
        copy_btn.clicked.connect(self._copy)
        copy_form.addRow("申请人", self.applicant)
        copy_form.addRow("关系", self.relationship)
        copy_form.addRow("份数", self.copies)
        copy_form.addRow("内容", self.copy_contents)
        copy_form.addRow("", copy_btn)
        layout.addWidget(copy_box)
        self.borrow_msg = QLabel("")
        self.borrow_msg.setWordWrap(True)
        layout.addWidget(self.borrow_msg)
        return page

    def _build_seal_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        refresh = QPushButton("刷新已归档病案")
        refresh.clicked.connect(self._refresh_seal)
        layout.addWidget(refresh)
        self.seal_table = QTableWidget(0, 5)
        self.seal_table.setHorizontalHeaderLabels(["病案号", "患者", "状态", "库位", "备注"])
        self.seal_table.cellClicked.connect(self._select_seal)
        layout.addWidget(self.seal_table, 1)
        box = QGroupBox("封存 / 启封 / 销毁")
        form = QFormLayout(box)
        self.seal_reason = QLineEdit()
        self.witness = QLineEdit()
        self.destroy_reason = QLineEdit()
        self.approved_by = QLineEdit()
        seal_btn = QPushButton("封存")
        seal_btn.clicked.connect(self._seal)
        unseal_btn = QPushButton("启封")
        unseal_btn.clicked.connect(self._unseal)
        destroy_btn = QPushButton("销毁")
        destroy_btn.clicked.connect(self._destroy)
        form.addRow("封存/启封原因", self.seal_reason)
        form.addRow("见证人", self.witness)
        form.addRow("销毁原因", self.destroy_reason)
        form.addRow("销毁审批人", self.approved_by)
        form.addRow(seal_btn, unseal_btn)
        form.addRow("", destroy_btn)
        layout.addWidget(box)
        self.seal_msg = QLabel("")
        self.seal_msg.setWordWrap(True)
        layout.addWidget(self.seal_msg)
        return page

    def _refresh(self) -> None:
        try:
            self.rows = self.api.list_archive_records(
                status=self.status_filter.currentData()
            )
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(self.rows))
        for row, record in enumerate(self.rows):
            values = [
                record.get("archive_no") or "—",
                record["patient_name"],
                TYPES.get(record["record_type"], record["record_type"]),
                str(record["page_count"]),
                STATUS.get(record["status"], record["status"]),
                record["storage_location"] or "—",
                str(record["created_at"])[:16].replace("T", " "),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.msg.setText(f"共 {len(self.rows)} 份病案")

    def _select(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.rows):
            self.current = self.rows[row]
            self.msg.setText(
                f"当前病案 {self.current.get('archive_no')} · "
                f"{STATUS.get(self.current['status'], self.current['status'])}"
            )

    def _selected(self, msg_label: QLabel) -> dict | None:
        if not self.current:
            msg_label.setText("请先选择一份病案")
            return None
        return self.current

    def _create(self) -> None:
        try:
            record = self.api.create_archive_record(
                {
                    "patient_id": self.patient_id.value(),
                    "encounter_id": self.encounter_id.value() or None,
                    "record_type": self.record_type.currentData(),
                    "note": self.note.text().strip(),
                }
            )
        except ApiError as e:
            self.msg.setText(f"建档失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText(f"已建档 {record['archive_no']}")
        self._refresh()

    def _archive(self) -> None:
        record = self._selected(self.msg)
        if not record:
            return
        try:
            self.api.archive_record(
                record["id"],
                {
                    "storage_location": self.location.text().strip(),
                    "page_count": self.pages.value(),
                    "completeness": self.completeness.currentData(),
                },
            )
        except ApiError as e:
            self.msg.setText(f"归档失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText("已归档上架")
        self._refresh()

    def _refresh_borrow(self) -> None:
        try:
            self.rows = self.api.list_archive_records()
        except ApiError as e:
            self.borrow_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.borrow_rows = [
            row for row in self.rows if row["status"] in ("archived", "borrowed")
        ]
        self.borrow_table.setRowCount(len(self.borrow_rows))
        for row, record in enumerate(self.borrow_rows):
            values = [
                record.get("archive_no") or "—",
                record["patient_name"],
                STATUS.get(record["status"], record["status"]),
                record["storage_location"] or "—",
                "",
                "",
            ]
            for col, value in enumerate(values):
                self.borrow_table.setItem(row, col, QTableWidgetItem(value))
        self.borrow_msg.setText(f"可借阅/借出中 {len(self.borrow_rows)} 份")

    def _select_borrow(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.borrow_rows):
            self.current = self.borrow_rows[row]

    def _borrow(self) -> None:
        record = self._selected(self.borrow_msg)
        if not record:
            return
        try:
            self.api.borrow_archive(
                record["id"],
                {
                    "borrower": self.borrower.text().strip(),
                    "department": self.department.text().strip(),
                    "due_days": self.days.value(),
                },
            )
        except ApiError as e:
            self.borrow_msg.setText(f"借阅失败（{e.status_code}）：{e.detail}")
            return
        self.borrow_msg.setText("已借出")
        self._refresh_borrow()

    def _return(self) -> None:
        record = self._selected(self.borrow_msg)
        if not record:
            return
        borrowing_id = record.get("active_borrowing_id")
        if not borrowing_id:
            self.borrow_msg.setText("该病案当前没有借阅记录")
            return
        try:
            self.api.return_archive(borrowing_id)
        except ApiError as e:
            self.borrow_msg.setText(f"归还失败（{e.status_code}）：{e.detail}")
            return
        self.borrow_msg.setText("已归还")
        self._refresh_borrow()

    def _copy(self) -> None:
        record = self._selected(self.borrow_msg)
        if not record:
            return
        try:
            self.api.copy_archive(
                record["id"],
                {
                    "applicant": self.applicant.text().strip(),
                    "relationship": self.relationship.text().strip() or "本人",
                    "copies": self.copies.value(),
                    "contents": self.copy_contents.text().strip(),
                },
            )
        except ApiError as e:
            self.borrow_msg.setText(f"复印登记失败（{e.status_code}）：{e.detail}")
            return
        self.borrow_msg.setText("复印申请已登记，待收费/完成")
        self._refresh_borrow()

    def _refresh_seal(self) -> None:
        try:
            self.rows = self.api.list_archive_records()
        except ApiError as e:
            self.seal_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.seal_rows = [
            row for row in self.rows if row["status"] in ("archived", "sealed")
        ]
        self.seal_table.setRowCount(len(self.seal_rows))
        for row, record in enumerate(self.seal_rows):
            values = [
                record.get("archive_no") or "—",
                record["patient_name"],
                STATUS.get(record["status"], record["status"]),
                record["storage_location"] or "—",
                record.get("note") or "",
            ]
            for col, value in enumerate(values):
                self.seal_table.setItem(row, col, QTableWidgetItem(value))
        self.seal_msg.setText(f"可封存/封存中 {len(self.seal_rows)} 份")

    def _select_seal(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.seal_rows):
            self.current = self.seal_rows[row]

    def _seal(self) -> None:
        record = self._selected(self.seal_msg)
        if not record:
            return
        try:
            self.api.seal_archive(
                record["id"],
                {"reason": self.seal_reason.text().strip(), "witness": self.witness.text().strip()},
            )
        except ApiError as e:
            self.seal_msg.setText(f"封存失败（{e.status_code}）：{e.detail}")
            return
        self.seal_msg.setText("已封存")
        self._refresh_seal()

    def _unseal(self) -> None:
        record = self._selected(self.seal_msg)
        if not record:
            return
        try:
            self.api.unseal_archive(
                record["id"],
                {"reason": self.seal_reason.text().strip(), "witness": self.witness.text().strip()},
            )
        except ApiError as e:
            self.seal_msg.setText(f"启封失败（{e.status_code}）：{e.detail}")
            return
        self.seal_msg.setText("已启封")
        self._refresh_seal()

    def _destroy(self) -> None:
        record = self._selected(self.seal_msg)
        if not record:
            return
        try:
            self.api.destroy_archive(
                record["id"],
                {
                    "reason": self.destroy_reason.text().strip(),
                    "approved_by": self.approved_by.text().strip(),
                },
            )
        except ApiError as e:
            self.seal_msg.setText(f"销毁失败（{e.status_code}）：{e.detail}")
            return
        self.seal_msg.setText("已销毁")
        self._refresh_seal()
