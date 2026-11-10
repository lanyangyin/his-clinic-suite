"""治疗室工作站：清创/换药/小处置排队、知情同意、处置记录。"""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
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
        self.templates: list[dict] = []
        self.template_edits: dict[str, QLineEdit] = {}
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_workbench_tab(), "今日工作台")
        self.tabs.addTab(self._build_queue_tab(), "治疗排队")
        self.tabs.addTab(self._build_handle_tab(), "处置记录")
        self.tabs.addTab(self._build_followup_tab(), "换药随访")
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

    def _build_queue_tab(self) -> QWidget:
        page = QWidget()
        self.queue_page = page
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
        self.template = QComboBox()
        self.template.currentIndexChanged.connect(self._on_template_changed)
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
        form.addRow("处置模板", self.template)
        form.addRow("处置名称", self.procedure)
        form.addRow("诊断", self.diagnosis)
        form.addRow("优先级", self.priority)
        form.addRow("收费项目 ID", self.charge_item_id)
        form.addRow("费用", self.price)
        form.addRow("", create)
        layout.addWidget(case_box)

        template_box = QGroupBox("模板记录项")
        self.template_form = QFormLayout(template_box)
        layout.addWidget(template_box)

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
        self._load_templates()
        return page

    def _build_handle_tab(self) -> QWidget:
        page = QWidget()
        self.handle_page = page
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

        material_box = QGroupBox("耗材扣减")
        material_form = QFormLayout(material_box)
        self.material_id = QSpinBox()
        self.material_id.setRange(1, 10_000_000)
        self.material_qty = QSpinBox()
        self.material_qty.setRange(1, 10000)
        self.material_warehouse = QLineEdit("总库")
        material_add = QPushButton("扣减耗材")
        material_add.clicked.connect(self._add_material)
        material_form.addRow("耗材 ID", self.material_id)
        material_form.addRow("数量", self.material_qty)
        material_form.addRow("库房", self.material_warehouse)
        material_form.addRow("", material_add)
        layout.addWidget(material_box)
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
        template_code = self.template.currentData()
        if template_code:
            definition = next(
                (row for row in self.templates if row["code"] == template_code), None
            )
            if definition:
                missing = [
                    field["label"]
                    for field in definition["fields"]
                    if field.get("required")
                    and not self.template_edits.get(field["key"], QLineEdit()).text().strip()
                ]
                if missing:
                    self.queue_msg.setText(f"请填写必填项：{'、'.join(missing)}")
                    return
        price_text = self.price.text().strip()
        payload = {
            "patient_id": self.patient_id.value(),
            "encounter_id": self.encounter_id.value() or None,
            "room_id": self.room.currentData(),
            "procedure_name": self.procedure.text().strip(),
            "template_code": self.template.currentData() or "",
            "template_data": {
                key: edit.text().strip()
                for key, edit in self.template_edits.items()
                if edit.text().strip()
            },
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
            self.tabs.setCurrentWidget(self.handle_page)
            self._load_case()

    def _load_case(self) -> None:
        try:
            case = self.api._request("GET", f"/treatment-room/cases/{self.case_id.value()}")
        except ApiError as e:
            self.handle_msg.setText(f"载入失败（{e.status_code}）：{e.detail}")
            return
        self.case_info.setText(
            f"{case['case_no']} · {case['patient_name']} · {case['procedure_name']} · "
            f"状态 {case['status']} · 费用 {case['price']:.2f} · 模板 {case.get('template_code') or '—'}"
        )
        try:
            patient = self.api.get_patient(case["patient_id"])
        except ApiError:
            patient = None
        if patient:
            gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "不详")
            age = patient.get("age")
            allergy = patient.get("allergy_label") or "不详"
            self.case_info.setText(
                self.case_info.text()
                + f" · {gender}/{age if age is not None else '—'}岁 · 过敏：{allergy}"
            )
            if patient.get("allergy_status") == "present":
                self.case_info.setStyleSheet("color:#b91c1c;font-weight:bold")
            else:
                self.case_info.setStyleSheet("")
        self.consent.setChecked(bool(case.get("consent")))
        self.anesthesia.setText(case.get("anesthesia") or "")
        self.findings.setText(case.get("findings") or "")
        self.procedure_detail.setText(case.get("procedure_detail") or "")
        self.sutures.setText(case.get("sutures") or "")
        self.dressing.setText(case.get("dressing") or "")
        self.materials.setText(case.get("materials") or "")
        self.complications.setText(case.get("complications") or "")
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

    def _add_material(self) -> None:
        try:
            row = self.api.treatment_room_material(
                self.case_id.value(),
                {
                    "material_id": self.material_id.value(),
                    "quantity": self.material_qty.value(),
                    "warehouse": self.material_warehouse.text().strip() or "总库",
                },
            )
        except ApiError as e:
            self.handle_msg.setText(f"耗材扣减失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText(f"已扣耗材 {row['name']} ×{row['quantity']}，材料费 {row['amount']:.2f}")

    def _load_templates(self) -> None:
        try:
            self.templates = self.api.treatment_room_templates()
        except ApiError as e:
            self.queue_msg.setText(f"加载模板失败（{e.status_code}）：{e.detail}")
            return
        self.template.clear()
        self.template.addItem("不使用模板", "")
        for row in self.templates:
            self.template.addItem(row["name"], row["code"])
        self._on_template_changed()

    def _on_template_changed(self) -> None:
        while self.template_form.count():
            item = self.template_form.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.template_edits = {}
        code = self.template.currentData()
        definition = next((row for row in self.templates if row["code"] == code), None)
        if not definition:
            return
        for field in definition["fields"]:
            edit = QLineEdit()
            self.template_edits[field["key"]] = edit
            label = field["label"] + (" *" if field.get("required") else "")
            self.template_form.addRow(label, edit)
        if not self.procedure.text().strip():
            self.procedure.setText(definition["name"])
        if definition.get("charge_item_id"):
            self.charge_item_id.setValue(int(definition["charge_item_id"]))
        if definition.get("price"):
            self.price.setText(f"{float(definition['price']):.2f}")


    def _build_followup_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        refresh = QPushButton("刷新待随访")
        refresh.clicked.connect(self._load_followups)
        complete = QPushButton("标记已随访")
        complete.clicked.connect(self._complete_followup)
        cancel = QPushButton("取消任务")
        cancel.clicked.connect(self._cancel_followup)
        top.addWidget(refresh)
        top.addWidget(complete)
        top.addWidget(cancel)
        top.addStretch(1)
        layout.addLayout(top)
        self.followup_table = QTableWidget(0, 5)
        self.followup_table.setHorizontalHeaderLabels(["患者", "日期", "目的", "备注", "状态"])
        layout.addWidget(self.followup_table, 1)

        result_box = QGroupBox("随访结果")
        result_form = QFormLayout(result_box)
        self.healing_score = QSpinBox()
        self.healing_score.setRange(0, 10)
        self.result_note = QLineEdit()
        self.result_note.setPlaceholderText("创面情况、渗出、愈合")
        self.photo_label = QLabel("未上传照片")
        upload = QPushButton("上传创面照片")
        upload.clicked.connect(self._upload_photo)
        self.next_followup = QCheckBox("生成下次随访")
        self.next_followup.setChecked(True)
        self.next_date = QDateEdit()
        self.next_date.setCalendarPopup(True)
        self.next_date.setDate(QDate.currentDate().addDays(2))
        self.next_purpose = QLineEdit("换药")
        result_form.addRow("愈合评分", self.healing_score)
        result_form.addRow("结果", self.result_note)
        result_form.addRow("照片", self.photo_label)
        result_form.addRow("", upload)
        result_form.addRow("下次随访", self.next_followup)
        result_form.addRow("下次日期", self.next_date)
        result_form.addRow("下次目的", self.next_purpose)
        layout.addWidget(result_box)
        self.followup_photo_path = ""
        self.followup_msg = QLabel("")
        layout.addWidget(self.followup_msg)
        self._load_followups()
        return page

    def _load_followups(self) -> None:
        try:
            self.followups = self.api.list_treatment_followups("pending")
        except ApiError as e:
            self.followup_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.followup_table.setRowCount(len(self.followups))
        for row, item in enumerate(self.followups):
            values = [item["patient_name"], str(item["due_date"]), item["purpose"], item["note"], item["status"]]
            for col, value in enumerate(values):
                self.followup_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.followup_msg.setText(f"待随访 {len(self.followups)} 条")

    def _selected_followup(self):
        row = self.followup_table.currentRow()
        if 0 <= row < len(getattr(self, "followups", [])):
            return self.followups[row]
        return None

    def _complete_followup(self) -> None:
        item = self._selected_followup()
        if not item:
            self.followup_msg.setText("请先选择随访任务")
            return
        payload = {
            "result_note": self.result_note.text().strip(),
            "healing_score": self.healing_score.value() or None,
            "next_purpose": self.next_purpose.text().strip() or "换药",
        }
        if self.next_followup.isChecked():
            payload["next_due_date"] = self.next_date.date().toString("yyyy-MM-dd")
        try:
            self.api.complete_treatment_followup(item["id"], payload)
        except ApiError as e:
            self.followup_msg.setText(f"操作失败（{e.status_code}）：{e.detail}")
            return
        self.followup_msg.setText("随访已完成")
        self.result_note.clear()
        self.healing_score.setValue(0)
        self.photo_label.setText("未上传照片")
        self.followup_photo_path = ""
        self._load_followups()

    def _upload_photo(self) -> None:
        item = self._selected_followup()
        if not item:
            self.followup_msg.setText("请先选择随访任务")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择创面照片", "", "图片 (*.jpg *.jpeg *.png *.webp)"
        )
        if not path:
            return
        try:
            result = self.api.upload_followup_photo(item["id"], path)
        except (ApiError, OSError) as e:
            self.followup_msg.setText(f"上传失败：{e}")
            return
        self.followup_photo_path = result.get("photo_path", "")
        self.photo_label.setText(f"已上传：{self.followup_photo_path.split('/')[-1]}")
        self.followup_msg.setText("照片已上传")

    def _cancel_followup(self) -> None:
        item = self._selected_followup()
        if not item:
            self.followup_msg.setText("请先选择随访任务")
            return
        try:
            self.api.cancel_treatment_followup(item["id"])
        except ApiError as e:
            self.followup_msg.setText(f"操作失败（{e.status_code}）：{e.detail}")
            return
        self._load_followups()


    def _build_workbench_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.wb_summary = QLabel("加载中…")
        self.wb_summary.setWordWrap(True)
        self.wb_summary.setStyleSheet("font-size:15px;font-weight:600;color:#0f172a")
        refresh = QPushButton("刷新工作台")
        refresh.clicked.connect(self._load_workbench)
        top.addWidget(self.wb_summary, 1)
        top.addWidget(refresh)
        layout.addLayout(top)

        self.wb_alerts = QLabel("")
        self.wb_alerts.setWordWrap(True)
        layout.addWidget(self.wb_alerts)

        layout.addWidget(QLabel("今日处置"))
        self.wb_cases = QTableWidget(0, 6)
        self.wb_cases.setHorizontalHeaderLabels(
            ["处置号", "患者", "处置", "状态", "优先级", "费用"]
        )
        self.wb_cases.cellClicked.connect(self._select_wb_case)
        layout.addWidget(self.wb_cases, 1)

        layout.addWidget(QLabel("到期 / 逾期随访"))
        self.wb_followups = QTableWidget(0, 4)
        self.wb_followups.setHorizontalHeaderLabels(["患者", "日期", "目的", "类型"])
        layout.addWidget(self.wb_followups, 1)
        self.wb_msg = QLabel("")
        layout.addWidget(self.wb_msg)
        self._load_workbench()
        return page

    def _load_workbench(self) -> None:
        try:
            data = self.api.treatment_room_workbench()
        except ApiError as e:
            self.wb_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.workbench_data = data
        self.wb_summary.setText(
            f"候诊 {data['waiting']}　处置中 {data['in_progress']}　"
            f"今日完成 {data['completed_today']}　待收费 {data['pending_count']} 笔 / "
            f"{data['pending_amount']:.2f} 元"
        )
        alerts = []
        if data["overdue"]:
            alerts.append(f"逾期随访 {len(data['overdue'])} 条")
        if data["due_today"]:
            alerts.append(f"今日随访 {len(data['due_today'])} 条")
        if data["low_stock"]:
            alerts.append(
                "低库存：" + "、".join(f"{row['name']}({row['quantity']})" for row in data["low_stock"][:5])
            )
        self.wb_alerts.setText("　".join(alerts) or "无待办提醒")
        self.wb_cases.setRowCount(len(data["cases"]))
        for row, case in enumerate(data["cases"]):
            values = [
                case["case_no"],
                case["patient_name"],
                case["procedure_name"],
                {"waiting": "候诊", "in_progress": "处置中", "completed": "已完成"}.get(
                    case["status"], case["status"]
                ),
                "加急" if case["priority"] == "urgent" else "普通",
                f"{case['price']:.2f}",
            ]
            for col, value in enumerate(values):
                self.wb_cases.setItem(row, col, QTableWidgetItem(str(value)))
        followups = [(row, "逾期") for row in data["overdue"]] + [
            (row, "今日") for row in data["due_today"]
        ]
        self.wb_followups.setRowCount(len(followups))
        for index, (row, kind) in enumerate(followups):
            values = [row["patient_name"], str(row["due_date"]), row["purpose"], kind]
            for col, value in enumerate(values):
                self.wb_followups.setItem(index, col, QTableWidgetItem(str(value)))
        self.wb_msg.setText(f"工作台已刷新（{data['date']}）")

    def _select_wb_case(self, row: int, _col: int) -> None:
        data = getattr(self, "workbench_data", None)
        if not data or not (0 <= row < len(data["cases"])):
            return
        self.case_id.setValue(data["cases"][row]["id"])
        self.tabs.setCurrentWidget(self.handle_page)
        self._load_case()
