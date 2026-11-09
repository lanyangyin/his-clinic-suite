"""检验科工作站：标本签收/拒收、结果录入、审核、危急值、报告打印。"""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.labels import zh


class LabWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.rows: list[dict] = []
        self.current: dict | None = None

        tabs = QTabWidget()
        tabs.addTab(self._build_work_tab(), "检验工作台")
        tabs.addTab(self._build_query_tab(), "报告查询")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def _build_work_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        top = QHBoxLayout()
        self.status_filter = QComboBox()
        for label, value in [
            ("全部未审核", "pending,collected,received,testing,reported,rejected"),
            ("待采样", "pending"),
            ("已采样", "collected"),
            ("已签收", "received"),
            ("检验中", "testing"),
            ("已报告", "reported"),
            ("标本拒收", "rejected"),
        ]:
            self.status_filter.addItem(label, value)
        self.priority_filter = QComboBox()
        self.priority_filter.addItem("全部优先级", None)
        self.priority_filter.addItem("加急", "urgent")
        self.priority_filter.addItem("普通", "routine")
        refresh = QPushButton("刷新工作列表")
        refresh.clicked.connect(self._refresh)
        top.addWidget(QLabel("状态"))
        top.addWidget(self.status_filter)
        top.addWidget(self.priority_filter)
        top.addWidget(refresh)
        layout.addLayout(top)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["申请", "标本号", "患者", "项目", "状态", "加急", "申请时间", "结果"]
        )
        self.table.cellClicked.connect(self._select_row)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        for text, handler in [
            ("采样", self._collect),
            ("签收", self._receive),
            ("拒收", self._reject),
            ("开始检验", self._start),
            ("打印报告", self._print_report),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)

        result_box = QGroupBox("结果 / 审核")
        form = QFormLayout(result_box)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        form.addRow(self.msg)
        values = QHBoxLayout()
        self.result_value = QLineEdit()
        self.result_value.setPlaceholderText("数值，如 12.5；文本项目可留空")
        self.result_unit = QLineEdit()
        self.result_unit.setPlaceholderText("单位")
        self.ref_low = QLineEdit()
        self.ref_low.setPlaceholderText("参考下限")
        self.ref_high = QLineEdit()
        self.ref_high.setPlaceholderText("参考上限")
        values.addWidget(QLabel("结果值"))
        values.addWidget(self.result_value)
        values.addWidget(QLabel("单位"))
        values.addWidget(self.result_unit)
        values.addWidget(QLabel("参考"))
        values.addWidget(self.ref_low)
        values.addWidget(self.ref_high)
        form.addRow(values)

        self.result_text = QLineEdit()
        self.result_text.setPlaceholderText("文本结果/备注，如 白细胞 6.2×10^9/L")
        form.addRow("文本结果", self.result_text)

        self.abnormal = QComboBox()
        for label, value in [("自动", ""), ("偏高 H", "H"), ("偏低 L", "L"), ("正常 N", "N")]:
            self.abnormal.addItem(label, value)
        form.addRow("异常标记", self.abnormal)

        critical_row = QHBoxLayout()
        self.critical = QCheckBox("危急值")
        self.critical_note = QLineEdit()
        self.critical_note.setPlaceholderText("危急值说明")
        self.notified_to = QLineEdit()
        self.notified_to.setPlaceholderText("已通知医生/科室")
        critical_row.addWidget(self.critical)
        critical_row.addWidget(self.critical_note)
        critical_row.addWidget(self.notified_to)
        form.addRow("危急值", critical_row)

        buttons = QHBoxLayout()
        report = QPushButton("出具报告")
        report.clicked.connect(self._report)
        review = QPushButton("审核报告")
        review.clicked.connect(self._review)
        critical = QPushButton("登记危急值")
        critical.clicked.connect(self._register_critical)
        buttons.addWidget(report)
        buttons.addWidget(review)
        buttons.addWidget(critical)
        form.addRow(buttons)
        layout.addWidget(result_box, 0)
        return page

    def _build_query_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        refresh = QPushButton("刷新已审核报告")
        refresh.clicked.connect(self._refresh_reviewed)
        top.addWidget(refresh)
        top.addStretch(1)
        layout.addLayout(top)
        self.reviewed_table = QTableWidget(0, 7)
        self.reviewed_table.setHorizontalHeaderLabels(
            ["报告号", "患者", "项目", "结果", "异常", "审核人", "报告时间"]
        )
        self.reviewed_table.cellClicked.connect(self._select_reviewed)
        layout.addWidget(self.reviewed_table, 1)
        self.query_msg = QLabel("")
        layout.addWidget(self.query_msg)
        self.reviewed_rows: list[dict] = []
        return page

    def _refresh(self) -> None:
        try:
            self.rows = self.api.lab_worklist(
                self.status_filter.currentData(), self.priority_filter.currentData()
            )
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(self.rows))
        for row, item in enumerate(self.rows):
            values = [
                str(item["id"]),
                item.get("specimen_no") or "—",
                item["patient_name"],
                item["item_name"],
                zh("lab_status", item["status"]),
                "加急" if item["priority"] == "urgent" else "普通",
                str(item["requested_at"])[:16].replace("T", " "),
                item.get("result_display") or "—",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.msg.setText(f"共 {len(self.rows)} 条检验申请")

    def _select_row(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.rows):
            self.current = self.rows[row]
            self.msg.setText(
                f"申请 {self.current['id']} · 标本 {self.current.get('specimen_no') or '—'} "
                f"· {zh('lab_status', self.current['status'])}"
            )
            self.result_unit.setText(self.current.get("result_unit") or "")
            low = self.current.get("reference_low")
            high = self.current.get("reference_high")
            self.ref_low.setText("" if low is None else f"{low:g}")
            self.ref_high.setText("" if high is None else f"{high:g}")

    def _selected_id(self) -> int | None:
        if not self.current:
            self.msg.setText("请先在列表中选择一条申请")
            return None
        return int(self.current["id"])

    def _run(self, action, success: str) -> None:
        request_id = self._selected_id()
        if request_id is None:
            return
        try:
            action(request_id)
        except ApiError as e:
            self.msg.setText(f"操作失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText(success)
        self._refresh()

    def _collect(self) -> None:
        self._run(self.api.collect_lab, "已采样")

    def _receive(self) -> None:
        self._run(self.api.receive_lab, "标本已签收")

    def _start(self) -> None:
        self._run(self.api.start_lab, "已开始检验")

    def _reject(self) -> None:
        request_id = self._selected_id()
        if request_id is None:
            return
        reason, ok = QInputDialog.getText(self, "标本拒收", "拒收原因（溶血/凝块/量不足等）")
        if not ok or not reason.strip():
            return
        try:
            self.api.reject_lab(request_id, reason.strip())
        except ApiError as e:
            self.msg.setText(f"拒收失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText("已拒收，通知重新采样")
        self._refresh()

    def _report(self) -> None:
        request_id = self._selected_id()
        if request_id is None:
            return
        try:
            value = (
                float(self.result_value.text())
                if self.result_value.text().strip()
                else None
            )
            low = float(self.ref_low.text()) if self.ref_low.text().strip() else None
            high = float(self.ref_high.text()) if self.ref_high.text().strip() else None
        except ValueError:
            self.msg.setText("结果值/参考范围必须是数字")
            return
        payload = {
            "result": self.result_text.text().strip(),
            "result_value": value,
            "result_unit": self.result_unit.text().strip(),
            "reference_low": low,
            "reference_high": high,
            "abnormal_flag": self.abnormal.currentData(),
            "critical_flag": self.critical.isChecked(),
            "critical_note": self.critical_note.text().strip(),
            "critical_notified_to": self.notified_to.text().strip(),
        }
        try:
            self.api.report_lab(request_id, payload)
        except ApiError as e:
            self.msg.setText(f"报告失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText("报告已出具，等待审核")
        self._refresh()

    def _review(self) -> None:
        self._run(self.api.review_lab, "报告已审核")

    def _register_critical(self) -> None:
        request_id = self._selected_id()
        if request_id is None:
            return
        note = self.critical_note.text().strip()
        notified = self.notified_to.text().strip()
        if not note:
            self.msg.setText("请填写危急值说明")
            return
        try:
            self.api.critical_lab(request_id, note, notified)
        except ApiError as e:
            self.msg.setText(f"登记失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText("危急值已登记")
        self._refresh()

    def _print_report(self) -> None:
        request_id = self._selected_id()
        if request_id is None:
            return
        QDesktopServices.openUrl(
            QUrl(f"{self.api.base_url}/print/lab-report/{request_id}")
        )

    def _refresh_reviewed(self) -> None:
        try:
            self.reviewed_rows = self.api.lab_worklist("reviewed")
        except ApiError as e:
            self.query_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.reviewed_table.setRowCount(len(self.reviewed_rows))
        for row, item in enumerate(self.reviewed_rows):
            values = [
                item.get("report_no") or "—",
                item["patient_name"],
                item["item_name"],
                item.get("result_display") or "—",
                item.get("abnormal_flag") or "—",
                item.get("reviewed_by") or "—",
                str(item.get("reported_at") or "")[:16].replace("T", " "),
            ]
            for col, value in enumerate(values):
                self.reviewed_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.query_msg.setText(f"已审核报告 {len(self.reviewed_rows)} 份")

    def _select_reviewed(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.reviewed_rows):
            item = self.reviewed_rows[row]
            self.query_msg.setText(
                f"报告 {item.get('report_no') or '—'} · {item['patient_name']} · "
                f"{item['item_name']} · {item.get('result_display') or '—'}"
            )
