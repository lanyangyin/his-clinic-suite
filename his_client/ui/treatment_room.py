"""治疗室工作站：清创/换药/小处置排队、知情同意、处置记录。"""
from PySide6.QtWidgets import (
    QCheckBox,
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


class TreatmentRoomWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.cases: list[dict] = []
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_queue_tab(), "治疗排队")
        self.tabs.addTab(self._build_handle_tab(), "处置记录")
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

    def _build_queue_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        room_box = QGroupBox("治疗室")
        room_form = QFormLayout(room_box)
        self.room_code = QLineEdit()
        self.room_name = QLineEdit()
        add_room = QPushButton("新增治疗室")
        add_room.clicked.connect(self._create_room)
        room_form.addRow("编码", self.room_code)
        room_form.addRow("名称", self.room_name)
        room_form.addRow("", add_room)
        layout.addWidget(room_box)

        case_box = QGroupBox("新建处置")
        form = QFormLayout(case_box)
        self.patient_id = QSpinBox()
        self.patient_id.setRange(1, 10_000_000)
        self.encounter_id = QSpinBox()
        self.encounter_id.setRange(0, 10_000_000)
        self.encounter_id.setSpecialValueText("不关联就诊")
        self.room = QComboBox()
        self.procedure = QLineEdit()
        self.diagnosis = QLineEdit()
        self.priority = QComboBox()
        self.priority.addItem("普通", "routine")
        self.priority.addItem("加急", "urgent")
        self.charge_item_id = QSpinBox()
        self.charge_item_id.setRange(0, 10_000_000)
        self.charge_item_id.setSpecialValueText("不关联收费项目")
        self.price = QLineEdit()
        self.price.setPlaceholderText("费用，空=收费项目价")
        create = QPushButton("创建处置")
        create.clicked.connect(self._create_case)
        form.addRow("患者 ID", self.patient_id)
        form.addRow("就诊 ID", self.encounter_id)
        form.addRow("治疗室", self.room)
        form.addRow("处置名称", self.procedure)
        form.addRow("诊断", self.diagnosis)
        form.addRow("优先级", self.priority)
        form.addRow("收费项目 ID", self.charge_item_id)
        form.addRow("费用", self.price)
        form.addRow("", create)
        layout.addWidget(case_box)

        refresh = QPushButton("刷新排队")
        refresh.clicked.connect(self._load_cases)
        layout.addWidget(refresh)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["处置号", "患者", "处置", "治疗室", "优先级", "状态", "费用"]
        )
        self.table.cellClicked.connect(self._select_case)
        layout.addWidget(self.table, 1)
        self.queue_msg = QLabel("")
        layout.addWidget(self.queue_msg)
        self._load_rooms()
        return page

    def _build_handle_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self.case_id = QSpinBox()
        self.case_id.setRange(1, 10_000_000)
        load = QPushButton("载入处置")
        load.clicked.connect(self._load_case)
        row.addWidget(QLabel("处置 ID"))
        row.addWidget(self.case_id)
        row.addWidget(load)
        layout.addLayout(row)
        self.case_info = QLabel("未载入")
        self.case_info.setWordWrap(True)
        layout.addWidget(self.case_info)

        start_box = QGroupBox("开始处置")
        start_form = QFormLayout(start_box)
        self.consent = QCheckBox("已签署知情同意")
        self.anesthesia = QLineEdit()
        self.findings = QLineEdit()
        start = QPushButton("开始")
        start.clicked.connect(self._start)
        start_form.addRow("知情同意", self.consent)
        start_form.addRow("麻醉", self.anesthesia)
        start_form.addRow("术中所见", self.findings)
        start_form.addRow("", start)
        layout.addWidget(start_box)

        complete_box = QGroupBox("完成处置")
        complete_form = QFormLayout(complete_box)
        self.procedure_detail = QLineEdit()
        self.sutures = QLineEdit()
        self.dressing = QLineEdit()
        self.materials = QLineEdit()
        self.complications = QLineEdit()
        complete = QPushButton("完成")
        complete.clicked.connect(self._complete)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self._cancel)
        complete_form.addRow("处置经过", self.procedure_detail)
        complete_form.addRow("缝合", self.sutures)
        complete_form.addRow("敷料", self.dressing)
        complete_form.addRow("耗材", self.materials)
        complete_form.addRow("并发症", self.complications)
        complete_form.addRow(complete, cancel)
        layout.addWidget(complete_box)
        self.handle_msg = QLabel("")
        layout.addWidget(self.handle_msg)
        return page

    def _create_room(self) -> None:
        try:
            self.api.create_treatment_room(
                {"code": self.room_code.text().strip(), "name": self.room_name.text().strip()}
            )
        except ApiError as e:
            self.queue_msg.setText(f"新增失败（{e.status_code}）：{e.detail}")
            return
        self.queue_msg.setText("治疗室已新增")
        self._load_rooms()

    def _load_rooms(self) -> None:
        try:
            rooms = self.api.list_treatment_rooms()
        except ApiError:
            return
        self.room.clear()
        self.room.addItem("不指定", None)
        for item in rooms:
            self.room.addItem(f"{item['code']} {item['name']}", item["id"])

    def _create_case(self) -> None:
        price_text = self.price.text().strip()
        payload = {
            "patient_id": self.patient_id.value(),
            "encounter_id": self.encounter_id.value() or None,
            "room_id": self.room.currentData(),
            "procedure_name": self.procedure.text().strip(),
            "diagnosis": self.diagnosis.text().strip(),
            "priority": self.priority.currentData(),
            "charge_item_id": self.charge_item_id.value() or None,
            "price": float(price_text) if price_text else 0,
        }
        try:
            case = self.api.create_treatment_room_case(payload)
        except (ApiError, ValueError) as e:
            self.queue_msg.setText(f"创建失败：{e}")
            return
        self.queue_msg.setText(f"已创建 {case['case_no']}")
        self._load_cases()

    def _load_cases(self) -> None:
        try:
            self.cases = self.api.list_treatment_room_cases()
        except ApiError as e:
            self.queue_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(self.cases))
        for row, case in enumerate(self.cases):
            values = [
                case["case_no"],
                case["patient_name"],
                case["procedure_name"],
                case.get("room_name") or "—",
                "加急" if case["priority"] == "urgent" else "普通",
                {"waiting": "候诊", "in_progress": "处置中", "completed": "已完成", "cancelled": "已取消"}.get(
                    case["status"], case["status"]
                ),
                f"{case['price']:.2f}",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.queue_msg.setText(f"处置 {len(self.cases)} 条")

    def _select_case(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.cases):
            self.case_id.setValue(self.cases[row]["id"])
            self.tabs.setCurrentIndex(1)
            self._load_case()

    def _load_case(self) -> None:
        try:
            case = self.api._request("GET", f"/treatment-room/cases/{self.case_id.value()}")
        except ApiError as e:
            self.handle_msg.setText(f"载入失败（{e.status_code}）：{e.detail}")
            return
        self.case_info.setText(
            f"{case['case_no']} · {case['patient_name']} · {case['procedure_name']} · "
            f"状态 {case['status']} · 费用 {case['price']:.2f}"
        )
        self.handle_msg.setText("已载入")

    def _start(self) -> None:
        try:
            self.api.start_treatment_room_case(
                self.case_id.value(),
                {
                    "consent": self.consent.isChecked(),
                    "anesthesia": self.anesthesia.text().strip(),
                    "findings": self.findings.text().strip(),
                },
            )
        except ApiError as e:
            self.handle_msg.setText(f"开始失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText("处置已开始")
        self._load_case()

    def _complete(self) -> None:
        try:
            self.api.complete_treatment_room_case(
                self.case_id.value(),
                {
                    "findings": self.findings.text().strip(),
                    "procedure_detail": self.procedure_detail.text().strip(),
                    "sutures": self.sutures.text().strip(),
                    "dressing": self.dressing.text().strip(),
                    "materials": self.materials.text().strip(),
                    "complications": self.complications.text().strip(),
                },
            )
        except ApiError as e:
            self.handle_msg.setText(f"完成失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText("处置已完成")
        self._load_case()

    def _cancel(self) -> None:
        try:
            self.api.cancel_treatment_room_case(self.case_id.value())
        except ApiError as e:
            self.handle_msg.setText(f"取消失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText("已取消")
        self._load_case()
