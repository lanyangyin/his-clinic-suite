"""手术室工作站：排班、安全核查、术中记录、器械清点、复苏。"""
from datetime import datetime, timedelta

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
from his_client.labels import zh


class SurgeryWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_schedule_tab(), "手术排班")
        self.tabs.addTab(self._build_intra_tab(), "安全核查 / 术中")
        self.tabs.addTab(self._build_recovery_tab(), "术后复苏")
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

    def _build_schedule_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        room_box = QGroupBox("手术间")
        room_form = QFormLayout(room_box)
        self.room_code = QLineEdit()
        self.room_name = QLineEdit()
        room_add = QPushButton("新增手术间")
        room_add.clicked.connect(self._create_room)
        room_form.addRow("编码", self.room_code)
        room_form.addRow("名称", self.room_name)
        room_form.addRow("", room_add)
        layout.addWidget(room_box)

        case_box = QGroupBox("手术排班")
        form = QFormLayout(case_box)
        self.sc_patient = QSpinBox()
        self.sc_patient.setRange(1, 10_000_000)
        self.sc_room = QComboBox()
        self.sc_procedure = QLineEdit()
        self.sc_diagnosis = QLineEdit()
        self.sc_surgeon = QLineEdit()
        self.sc_anesthesia = QLineEdit()
        self.sc_time = QLineEdit()
        self.sc_time.setPlaceholderText("YYYY-MM-DDTHH:MM:SS")
        self.sc_time.setText((datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT09:00:00"))
        create = QPushButton("创建手术")
        create.clicked.connect(self._create_case)
        form.addRow("患者 ID", self.sc_patient)
        form.addRow("手术间", self.sc_room)
        form.addRow("手术名称", self.sc_procedure)
        form.addRow("诊断", self.sc_diagnosis)
        form.addRow("术者", self.sc_surgeon)
        form.addRow("麻醉", self.sc_anesthesia)
        form.addRow("计划时间", self.sc_time)
        form.addRow("", create)
        layout.addWidget(case_box)

        top = QHBoxLayout()
        refresh = QPushButton("刷新手术列表")
        refresh.clicked.connect(self._load_cases)
        top.addWidget(refresh)
        top.addStretch(1)
        layout.addLayout(top)
        self.case_table = QTableWidget(0, 7)
        self.case_table.setHorizontalHeaderLabels(
            ["手术号", "患者", "手术", "术者", "手术间", "状态", "计划时间"]
        )
        self.case_table.cellClicked.connect(self._select_case)
        layout.addWidget(self.case_table, 1)
        self.schedule_msg = QLabel("")
        layout.addWidget(self.schedule_msg)
        self._load_rooms()
        return page

    def _build_intra_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.case_id = QSpinBox()
        self.case_id.setRange(1, 10_000_000)
        load = QPushButton("载入手术")
        load.clicked.connect(self._load_case)
        top.addWidget(QLabel("手术 ID"))
        top.addWidget(self.case_id)
        top.addWidget(load)
        layout.addLayout(top)
        self.case_info = QLabel("未载入")
        self.case_info.setWordWrap(True)
        layout.addWidget(self.case_info)

        safety_box = QGroupBox("安全核查")
        safety = QVBoxLayout(safety_box)
        self.checklist = QLineEdit()
        self.checklist.setPlaceholderText("核查内容，如 身份/部位/过敏史")
        safety.addWidget(self.checklist)
        row = QHBoxLayout()
        for phase, label in (("sign_in", "术前核查"), ("time_out", "Time Out"), ("sign_out", "离室核查")):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, p=phase: self._safety(p))
            row.addWidget(button)
        start = QPushButton("开始手术")
        start.clicked.connect(self._start)
        complete = QPushButton("结束手术")
        complete.clicked.connect(self._complete)
        row.addWidget(start)
        row.addWidget(complete)
        safety.addLayout(row)
        layout.addWidget(safety_box)

        record_box = QGroupBox("术中记录")
        record_form = QFormLayout(record_box)
        self.findings = QLineEdit()
        self.procedure_detail = QLineEdit()
        self.implants = QLineEdit()
        self.specimens = QLineEdit()
        self.blood_loss = QSpinBox()
        self.blood_loss.setRange(0, 100000)
        save = QPushButton("保存术中记录")
        save.clicked.connect(self._save_record)
        record_form.addRow("术中所见", self.findings)
        record_form.addRow("手术经过", self.procedure_detail)
        record_form.addRow("植入物", self.implants)
        record_form.addRow("标本", self.specimens)
        record_form.addRow("出血 ml", self.blood_loss)
        record_form.addRow("", save)
        layout.addWidget(record_box)

        count_box = QGroupBox("器械清点")
        count_form = QFormLayout(count_box)
        self.count_phase = QComboBox()
        self.count_phase.addItem("术前", "before")
        self.count_phase.addItem("术后", "after")
        self.count_item = QLineEdit()
        self.count_expected = QSpinBox()
        self.count_actual = QSpinBox()
        self.count_expected.setRange(0, 10000)
        self.count_actual.setRange(0, 10000)
        add_count = QPushButton("保存清点")
        add_count.clicked.connect(self._add_count)
        count_form.addRow("阶段", self.count_phase)
        count_form.addRow("物品", self.count_item)
        count_form.addRow("应有", self.count_expected)
        count_form.addRow("实有", self.count_actual)
        count_form.addRow("", add_count)
        layout.addWidget(count_box)

        package_row = QHBoxLayout()
        self.package_id = QSpinBox()
        self.package_id.setRange(1, 10_000_000)
        attach = QPushButton("关联 CSSD 器械包")
        attach.clicked.connect(self._attach_package)
        package_row.addWidget(QLabel("器械包 ID"))
        package_row.addWidget(self.package_id)
        package_row.addWidget(attach)
        layout.addLayout(package_row)
        self.intra_msg = QLabel("")
        self.intra_msg.setWordWrap(True)
        layout.addWidget(self.intra_msg)
        return page

    def _build_recovery_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.recovery_case = QSpinBox()
        self.recovery_case.setRange(1, 10_000_000)
        self.vitals = QLineEdit()
        self.score = QSpinBox()
        self.score.setRange(0, 10)
        self.recovery_note = QLineEdit()
        save = QPushButton("登记复苏")
        save.clicked.connect(self._save_recovery)
        form.addRow("手术 ID", self.recovery_case)
        form.addRow("生命体征", self.vitals)
        form.addRow("评分", self.score)
        form.addRow("备注", self.recovery_note)
        form.addRow("", save)
        layout.addLayout(form)
        self.recovery_msg = QLabel("")
        layout.addWidget(self.recovery_msg)
        layout.addStretch(1)
        return page

    def _create_room(self) -> None:
        try:
            self.api.create_surgery_room(
                {"code": self.room_code.text().strip(), "name": self.room_name.text().strip()}
            )
        except ApiError as e:
            self.schedule_msg.setText(f"新增失败（{e.status_code}）：{e.detail}")
            return
        self.schedule_msg.setText("手术间已新增")
        self._load_rooms()

    def _load_rooms(self) -> None:
        try:
            rooms = self.api.list_surgery_rooms()
        except ApiError as e:
            self.schedule_msg.setText(f"加载手术间失败（{e.status_code}）：{e.detail}")
            return
        self.sc_room.clear()
        self.sc_room.addItem("不指定", None)
        for room in rooms:
            self.sc_room.addItem(f"{room['code']} {room['name']}", room["id"])

    def _create_case(self) -> None:
        payload = {
            "patient_id": self.sc_patient.value(),
            "room_id": self.sc_room.currentData(),
            "procedure_name": self.sc_procedure.text().strip(),
            "diagnosis": self.sc_diagnosis.text().strip(),
            "surgeon": self.sc_surgeon.text().strip(),
            "anesthesia_type": self.sc_anesthesia.text().strip(),
            "scheduled_at": self.sc_time.text().strip(),
        }
        try:
            case = self.api.create_surgery_case(payload)
        except ApiError as e:
            self.schedule_msg.setText(f"排班失败（{e.status_code}）：{e.detail}")
            return
        self.schedule_msg.setText(f"已排班 {case['surgery_no']}")
        self._load_cases()

    def _load_cases(self) -> None:
        try:
            self.cases = self.api.list_surgery_cases()
        except ApiError as e:
            self.schedule_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.case_table.setRowCount(len(self.cases))
        for row, case in enumerate(self.cases):
            values = [
                case["surgery_no"],
                case["patient_name"],
                case["procedure_name"],
                case["surgeon"],
                case.get("room_name") or "—",
                {"scheduled": "已排班", "in_progress": "手术中", "completed": "已完成", "cancelled": "已取消"}.get(
                    case["status"], case["status"]
                ),
                str(case["scheduled_at"])[:16].replace("T", " "),
            ]
            for col, value in enumerate(values):
                self.case_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.schedule_msg.setText(f"手术 {len(self.cases)} 台")

    def _select_case(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.cases):
            self.case_id.setValue(self.cases[row]["id"])
            self.recovery_case.setValue(self.cases[row]["id"])
            self._load_case()
            self.tabs.setCurrentIndex(1)

    def _load_case(self) -> None:
        try:
            data = self.api.surgery_case_detail(self.case_id.value())
        except ApiError as e:
            self.intra_msg.setText(f"载入失败（{e.status_code}）：{e.detail}")
            return
        case = data["case"]
        self.case_info.setText(
            f"{case['surgery_no']} · 患者 {case['patient_id']} · {case['procedure_name']} · "
            f"状态 {case['status']} · 核查 {len(data['checks'])} · 记录 {len(data['records'])} · "
            f"清点 {len(data['counts'])} · 复苏 {len(data['recovery'])}"
        )
        self.intra_msg.setText("手术已载入")

    def _safety(self, phase: str) -> None:
        try:
            self.api.surgery_safety(self.case_id.value(), phase, self.checklist.text().strip())
        except ApiError as e:
            self.intra_msg.setText(f"核查失败（{e.status_code}）：{e.detail}")
            return
        self.intra_msg.setText(f"安全核查完成：{phase}")
        self._load_case()

    def _start(self) -> None:
        try:
            self.api.start_surgery(self.case_id.value())
        except ApiError as e:
            self.intra_msg.setText(f"开始失败（{e.status_code}）：{e.detail}")
            return
        self.intra_msg.setText("手术已开始")
        self._load_case()

    def _save_record(self) -> None:
        try:
            self.api.surgery_record(
                self.case_id.value(),
                {
                    "findings": self.findings.text().strip(),
                    "procedure_detail": self.procedure_detail.text().strip(),
                    "implants": self.implants.text().strip(),
                    "specimens": self.specimens.text().strip(),
                    "blood_loss_ml": self.blood_loss.value(),
                },
            )
        except ApiError as e:
            self.intra_msg.setText(f"记录失败（{e.status_code}）：{e.detail}")
            return
        self.intra_msg.setText("术中记录已保存")
        self._load_case()

    def _add_count(self) -> None:
        try:
            row = self.api.surgery_count(
                self.case_id.value(),
                {
                    "phase": self.count_phase.currentData(),
                    "item_name": self.count_item.text().strip(),
                    "expected": self.count_expected.value(),
                    "actual": self.count_actual.value(),
                },
            )
        except ApiError as e:
            self.intra_msg.setText(f"清点失败（{e.status_code}）：{e.detail}")
            return
        self.intra_msg.setText("清点相符" if row["matched"] else "清点不符")
        self._load_case()

    def _complete(self) -> None:
        try:
            self.api.complete_surgery(self.case_id.value())
        except ApiError as e:
            self.intra_msg.setText(f"结束失败（{e.status_code}）：{e.detail}")
            return
        self.intra_msg.setText("手术已结束")
        self._load_case()

    def _attach_package(self) -> None:
        try:
            row = self.api.attach_surgery_package(
                self.case_id.value(), self.package_id.value()
            )
        except ApiError as e:
            self.intra_msg.setText(f"关联失败（{e.status_code}）：{e.detail}")
            return
        self.intra_msg.setText(f"已关联器械包 {row['package_code']}")

    def _save_recovery(self) -> None:
        try:
            row = self.api.surgery_recovery(
                self.recovery_case.value(),
                {
                    "vitals": self.vitals.text().strip(),
                    "score": self.score.value(),
                    "note": self.recovery_note.text().strip(),
                },
            )
        except ApiError as e:
            self.recovery_msg.setText(f"复苏登记失败（{e.status_code}）：{e.detail}")
            return
        self.recovery_msg.setText(f"复苏已登记，评分 {row['score']}")
