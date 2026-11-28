"""影像科工作站：待检查列表、报告回传。"""
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from his_client.api import ApiClient, ApiError
from his_client.ui.pagination import PaginationBar
from his_client.ui.print_preview import open_print_preview
from his_client.ui.theme import apply_theme


class RadiologyWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.rows: list[dict] = []
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("影像科工作站")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        self.status_filter = QComboBox()
        self.status_filter.addItem("待处理（含DC）", "pending,dc")
        self.status_filter.addItem("已报告", "reported")
        self.status_filter.addItem("已审核", "reviewed")
        self.template_combo = QComboBox()
        self.template_combo.addItem("报告模板", None)
        self.template_combo.currentIndexChanged.connect(self._apply_template)
        self.priority_filter = QComboBox()
        self.priority_filter.addItem("全部优先级", None)
        self.priority_filter.addItem("加急", "urgent")
        self.priority_filter.addItem("普通", "routine")
        self.priority_filter.currentIndexChanged.connect(lambda _index: self._load())
        self.status_filter.currentIndexChanged.connect(lambda _index: self._load())
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.template_combo)
        top.addWidget(self.priority_filter)
        top.addWidget(self.status_filter)
        top.addWidget(refresh)
        layout.addLayout(top)
        splitter = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["影像号", "患者", "检查项目", "优先级", "申请医生", "时间", "状态", "报告人", "审核人"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._select)
        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table, 1)
        self.pager = PaginationBar((20, 50, 100, 200))
        self.pager.pageChanged.connect(lambda _page: self._render_page())
        self.pager.pageSizeChanged.connect(lambda _size: self._render_page())
        table_layout.addWidget(self.pager)
        splitter.addWidget(table_page)
        detail = QWidget()
        dl = QVBoxLayout(detail)
        self.info = QLabel("请选择一条检查申请")
        self.report = QTextEdit()
        self.report.setPlaceholderText("影像所见")
        self.image_url = QLineEdit()
        self.image_url.setPlaceholderText("PACS 图像地址（可选）")
        view_image = QPushButton("打开图像")
        view_image.clicked.connect(self._open_image)
        submit = QPushButton("提交报告")
        submit.clicked.connect(self._submit)
        self.review_note = QLineEdit()
        self.review_note.setPlaceholderText("审核意见 / 退回原因")
        approve = QPushButton("审核通过")
        approve.clicked.connect(lambda: self._review(True))
        reject = QPushButton("退回报告")
        reject.clicked.connect(lambda: self._review(False))
        print_report = QPushButton("打印报告")
        print_report.clicked.connect(self._print_report)
        dl.addWidget(self.info)
        dl.addWidget(self.report, 1)
        self.impression = QTextEdit()
        self.impression.setPlaceholderText("诊断意见")
        dl.addWidget(self.impression)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_url, 1)
        image_row.addWidget(view_image)
        dl.addLayout(image_row)
        dicom_row = QHBoxLayout()
        self.study_uid = QLineEdit()
        self.study_uid.setPlaceholderText("StudyUID")
        self.series_uid = QLineEdit()
        self.series_uid.setPlaceholderText("SeriesUID")
        self.modality = QLineEdit()
        self.modality.setPlaceholderText("Modality")
        self.measurements = QLineEdit()
        self.measurements.setPlaceholderText("测量值（如 结节 8mm）")
        dicom_row.addWidget(self.study_uid, 2)
        dicom_row.addWidget(self.series_uid, 2)
        dicom_row.addWidget(self.modality, 1)
        dl.addLayout(dicom_row)
        dl.addWidget(self.measurements)
        dl.addWidget(self.review_note)
        actions = QHBoxLayout()
        actions.addWidget(submit)
        actions.addWidget(approve)
        actions.addWidget(reject)
        actions.addWidget(print_report)
        dl.addLayout(actions)
        self.msg = QLabel("")
        dl.addWidget(self.msg)
        splitter.addWidget(detail)
        splitter.setSizes([320, 320])
        layout.addWidget(splitter, 1)
        self._load_templates()
        self._load()

    def _load_templates(self) -> None:
        try:
            templates = self.api.list_imaging_templates()
        except ApiError:
            return
        for row in templates:
            self.template_combo.addItem(row.get("name") or "模板", row)

    def _apply_template(self, _index: int) -> None:
        row = self.template_combo.currentData()
        if not row:
            return
        self.report.setPlainText(row.get("findings") or "")
        self.impression.setPlainText(row.get("impression") or "")

    def _load(self) -> None:
        try:
            self.rows = self.api.list_imaging_worklist(
                self.status_filter.currentData() or "pending",
                self.priority_filter.currentData(),
            )
        except ApiError as e:
            self.msg.setText(f"加载失败：{e.detail}")
            return
        self.pager.set_page(1)
        self.pager.set_total(len(self.rows))
        self._render_page()

    def _render_page(self) -> None:
        size = self.pager.page_size()
        start = (self.pager.page() - 1) * size
        self.page_rows = self.rows[start:start + size]
        self.table.setRowCount(len(self.page_rows))
        for i, item in enumerate(self.page_rows):
            values = [
                item.get("accession_no") or "",
                f"{item.get('patient_name') or ''} {item.get('patient_no') or ''}",
                item.get("item_name") or "",
                "加急" if item.get("priority") == "urgent" else "普通",
                item.get("requested_by") or "",
                str(item.get("requested_at") or "")[:16].replace("T", " "),
                {"pending": "待检查", "reported": "已报告", "reviewed": "已审核", "rejected": "已退回"}.get(item.get("status"), item.get("status") or ""),
                item.get("reported_by") or "",
                item.get("reviewed_by") or "",
            ]
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        label = {
            "pending": "待检查",
            "reported": "已报告",
            "reviewed": "已审核",
            "rejected": "已退回",
        }.get(self.status_filter.currentData() or "pending", "检查")
        self.msg.setText(f"{label} {len(self.rows)} 条")

    def _select(self, row: int, _col: int) -> None:
        if 0 <= row < len(getattr(self, "page_rows", [])):
            item = getattr(self, "page_rows", [])[row]
            try:
                detail = self.api.get_imaging_request(item["id"])
                item = {**item, **{k: v for k, v in detail.items() if v is not None}}
                getattr(self, "page_rows", [])[row] = item
            except ApiError:
                pass
            self.info.setText(
                f"{item.get('accession_no')}　{item.get('patient_name')}　"
                f"{item.get('item_name')}　申请：{item.get('requested_by')}"
            )
            self.report.setPlainText(item.get("findings") or item.get("report") or "")
            self.impression.setPlainText(item.get("impression") or "")
            self.study_uid.setText(item.get("study_uid") or "")
            self.series_uid.setText(item.get("series_uid") or "")
            self.modality.setText(item.get("modality") or "")
            self.measurements.setText(item.get("measurements") or "")

    def _print_report(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(getattr(self, "page_rows", [])):
            self.msg.setText("请先选择检查申请")
            return
        item = getattr(self, "page_rows", [])[row]
        if item.get("status") not in ("reported", "reviewed"):
            self.msg.setText("只有已报告/已审核的检查可以打印")
            return
        open_print_preview(
            self,
            f"{self.api.base_url}/print/imaging-report/{item['id']}",
            "检查报告单打印预览",
        )

    def _open_image(self) -> None:
        url = self.image_url.text().strip()
        if not url:
            self.msg.setText("该检查没有 PACS 图像地址")
            return
        if not QDesktopServices.openUrl(QUrl(url)):
            self.msg.setText("无法打开图像地址，请复制到 PACS 客户端查看")

    def _submit(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(getattr(self, "page_rows", [])):
            self.msg.setText("请先选择检查申请")
            return
        text = self.report.toPlainText().strip()
        if not text:
            self.msg.setText("报告内容不能为空")
            return
        try:
            self.api.report_imaging(
                getattr(self, "page_rows", [])[row]["id"],
                text,
                self.image_url.text().strip(),
                self.impression.toPlainText().strip(),
                self.study_uid.text().strip(),
                self.series_uid.text().strip(),
                self.modality.text().strip(),
                self.measurements.text().strip(),
            )
        except ApiError as e:
            self.msg.setText(f"提交失败：{e.detail}")
            return
        self.report.clear()
        self.impression.clear()
        self.image_url.clear()
        self.study_uid.clear()
        self.series_uid.clear()
        self.modality.clear()
        self.measurements.clear()
        self._load()
        self.msg.setText("报告已提交")

    def _review(self, approve: bool) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(getattr(self, "page_rows", [])):
            self.msg.setText("请先选择检查申请")
            return
        item = getattr(self, "page_rows", [])[row]
        if item.get("status") != "reported":
            self.msg.setText("只有已报告检查可以审核")
            return
        note = self.review_note.text().strip()
        if not approve and not note:
            self.msg.setText("退回报告必须填写原因")
            return
        try:
            self.api.review_imaging(item["id"], approve, note)
        except ApiError as e:
            self.msg.setText(f"审核失败：{e.detail}")
            return
        self.review_note.clear()
        self.msg.setText("报告已审核" if approve else "报告已退回")
        self._load()
