"""医生工作站：叫号接诊、结构化病历、开方（含用法）、检验检查开单、治疗开单。"""
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QCompleter,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.config import load_config
from his_client.labels import zh
from his_client.ui.patient_banner import PatientBanner
from his_client.ui.payment import PaymentPanel

_RECORD_FIELDS = [
    ("chief_complaint", "主诉", 200),
    ("present_illness", "现病史", 1000),
    ("past_history", "既往史", 1000),
    ("physical_exam", "体格检查", 1000),
    ("treatment_advice", "处理意见", 500),
]


class DoctorWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.insurance_enabled = load_config().insurance_enabled
        self.banner = PatientBanner()
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_workbench_tab(), "门诊工作台")
        self.tabs.addTab(self._build_register_tab(), "挂号")
        self.tabs.addTab(self._build_reception_tab(), "接诊")
        self.tabs.addTab(self._build_record_tab(), "病历")
        self.tabs.addTab(self._build_history_tab(), "历史诊疗")
        self.tabs.addTab(self._build_prescription_tab(), "开方")
        self.tabs.addTab(PaymentPanel(api), "收费")
        self.tabs.addTab(self._build_exam_tab(), "检验 / 检查")
        self.tabs.addTab(self._build_treatment_tab(), "治疗")
        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        layout.addWidget(self.tabs)
        self._load_diagnoses()
        self._install_shortcuts()
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_refresh)
        self.auto_timer.start(15000)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, _index: int) -> None:
        if "开方" in self.tabs.tabText(self.tabs.currentIndex()) and not hasattr(self, "drug_rows"):
            self._load_drugs()

    def _print_current(self) -> None:
        encounter_id = self.banner.encounter_id
        if not encounter_id:
            self.wb_summary.setText("请先选择患者并接诊")
            return
        QDesktopServices.openUrl(
            QUrl(self.api.prescription_print_url(encounter_id))
        )

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("F2"), self, activated=self._focus_workbench_search)
        QShortcut(QKeySequence("F3"), self, activated=self._load_workbench)
        QShortcut(QKeySequence("F4"), self, activated=self._start_workbench)
        QShortcut(QKeySequence("F5"), self, activated=self._wb_record)
        QShortcut(QKeySequence("F6"), self, activated=self._wb_prescribe)
        QShortcut(QKeySequence("F8"), self, activated=lambda: self._switch_tab("收费"))
        QShortcut(QKeySequence("F9"), self, activated=self._print_current)
        QShortcut(QKeySequence("Esc"), self, activated=self._clear_workbench_search)

    def _focus_workbench_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.wb_search.setFocus()
        self.wb_search.selectAll()

    def _clear_workbench_search(self) -> None:
        if self.wb_search.text():
            self.wb_search.clear()

    def _auto_refresh(self) -> None:
        if self.tabs.currentIndex() == 0 and self.isVisible():
            self._load_workbench()

    # ---------- 门诊工作台 ----------
    def _build_workbench_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        top.addWidget(QLabel("今日门诊队列（待接诊 + 今日已接诊）"))
        self.wb_search = QLineEdit()
        self.wb_search.setPlaceholderText("F2 搜索姓名/电话/挂号号")
        self.wb_search.setClearButtonEnabled(True)
        self.wb_search.textChanged.connect(self._filter_workbench)
        refresh = QPushButton("刷新队列")
        refresh.clicked.connect(self._load_workbench)
        top.addWidget(self.wb_search, 1)
        top.addWidget(refresh)
        top.addStretch(1)
        layout.addLayout(top)

        self.wb_table = QTableWidget(0, 7)
        self.wb_table.setHorizontalHeaderLabels(
            ["挂号", "患者", "医生", "挂号状态", "就诊", "诊断", "待缴"]
        )
        self.wb_table.cellClicked.connect(self._select_workbench)
        self.wb_table.cellDoubleClicked.connect(
            lambda row, _col: self._start_workbench_row(row)
        )

        self.wb_patient = QLabel("请选择患者")
        self.wb_patient.setStyleSheet("font-weight:bold;color:#0f172a")
        layout.addWidget(self.wb_patient)

        critical_box = QGroupBox("危急值待确认")
        critical_layout = QVBoxLayout(critical_box)
        self.critical_table = QTableWidget(0, 5)
        self.critical_table.setHorizontalHeaderLabels(
            ["患者", "项目", "结果", "报告时间", "超时"]
        )
        self.critical_table.setMaximumHeight(120)
        self.critical_table.cellClicked.connect(self._select_critical)
        critical_layout.addWidget(self.critical_table)
        critical_row = QHBoxLayout()
        self.critical_note = QLineEdit()
        self.critical_note.setPlaceholderText("确认备注，如 已电话回读")
        ack = QPushButton("确认危急值")
        ack.clicked.connect(self._ack_critical)
        critical_row.addWidget(self.critical_note)
        critical_row.addWidget(ack)
        critical_layout.addLayout(critical_row)
        self.critical_msg = QLabel("")
        critical_layout.addWidget(self.critical_msg)
        layout.addWidget(critical_box)

        row = QHBoxLayout()
        self.wb_diagnosis_code = QComboBox()
        self.wb_diagnosis_code.addItem("诊断编码（可选）", "")
        self.wb_diagnosis_code.currentIndexChanged.connect(self._diagnosis_selected)
        self.wb_diagnosis = QLineEdit()
        self.wb_diagnosis.setPlaceholderText("诊断，如 急性上呼吸道感染")
        self.wb_start = QPushButton("开始接诊")
        self.wb_start.clicked.connect(self._start_workbench)
        row.addWidget(QLabel("诊断"))
        row.addWidget(self.wb_diagnosis_code)
        row.addWidget(self.wb_diagnosis)
        row.addWidget(self.wb_start)
        layout.addLayout(row)

        actions = QHBoxLayout()
        for text, handler in [
            ("写病历", self._wb_record),
            ("开方", self._wb_prescribe),
            ("开检验", self._wb_exam),
            ("开治疗", self._wb_treat),
            ("历史诊疗", self._wb_history),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)

        self.wb_summary = QLabel("")
        self.wb_summary.setWordWrap(True)
        layout.addWidget(self.wb_summary)
        self.wb_fee_table = QTableWidget(0, 4)
        self.wb_fee_table.setHorizontalHeaderLabels(["项目", "数量", "金额", "状态"])
        layout.addWidget(self.wb_fee_table, 1)
        return page

    def _load_diagnoses(self) -> None:
        try:
            rows = self.api.list_diagnoses()
        except ApiError:
            return
        for combo in (
            getattr(self, "wb_diagnosis_code", None),
            getattr(self, "rec_diagnosis_code", None),
        ):
            if combo is None:
                continue
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("诊断编码（可选）", "")
            for row in rows:
                combo.addItem(f"{row['code']} {row['name']}", row["code"])
            combo.blockSignals(False)

    def _diagnosis_selected(self, _index: int) -> None:
        combo = self.sender()
        code = combo.currentData() if combo else ""
        text = combo.currentText() if combo else ""
        name = text.split(" ", 1)[1] if " " in text else ""
        target = (
            self.wb_diagnosis
            if combo is getattr(self, "wb_diagnosis_code", None)
            else getattr(self, "rec_diagnosis", None)
        )
        if code and target is not None:
            target.setText(name)

    def _load_workbench(self) -> None:
        try:
            self.workbench_all = self.api.doctor_worklist()
        except ApiError as e:
            self.wb_summary.setText(f"加载队列失败（{e.status_code}）：{e.detail}")
            return
        self._filter_workbench()
        self._load_critical_alerts()

    def _filter_workbench(self) -> None:
        term = self.wb_search.text().strip().lower() if hasattr(self, "wb_search") else ""
        rows = getattr(self, "workbench_all", getattr(self, "workbench_rows", []))
        if term:
            rows = [
                item
                for item in rows
                if term in str(item.get("patient_name", "")).lower()
                or term in str(item.get("phone", "")).lower()
                or term in str(item.get("registration_id", "")).lower()
            ]
        self.workbench_rows = rows
        self.wb_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            gender = {"male": "男", "female": "女"}.get(item.get("gender"), "不详")
            age = item.get("age")
            allergy = item.get("allergy_label") or "不详"
            level = item.get("triage_level")
            level_text = f"[{level}级]" if level else ""
            values = [
                str(item["registration_id"]),
                f"{level_text}{item['patient_name']} · {gender}/{age if age is not None else '—'} · {allergy}",
                item["doctor_name"],
                zh("registration_status", item["registration_status"]),
                str(item.get("encounter_id") or "—"),
                (
                    f"{item.get('diagnosis_code')} {item.get('diagnosis')}".strip()
                    or "—"
                ),
                f"{item.get('pending_amount', 0):.2f}",
            ]
            for col, value in enumerate(values):
                self.wb_table.setItem(row, col, QTableWidgetItem(str(value)))
        total = len(getattr(self, "workbench_all", rows))
        self.wb_summary.setText(
            f"显示 {len(rows)} / 今日 {total} 人" if term else f"今日队列 {total} 人"
        )
        current = getattr(self, "wb_current", None)
        if current:
            for index, item in enumerate(rows):
                if item["registration_id"] == current.get("registration_id"):
                    self.wb_table.selectRow(index)
                    break

    def _start_workbench_row(self, row: int) -> None:
        if 0 <= row < len(getattr(self, "workbench_rows", [])):
            self.wb_table.selectRow(row)
            self._select_workbench(row, 0)
            if self.wb_start.isEnabled():
                self._start_workbench()

    def _load_critical_alerts(self) -> None:
        try:
            alerts = self.api.critical_alerts()
        except ApiError as e:
            self.critical_msg.setText(f"危急值加载失败（{e.status_code}）：{e.detail}")
            return
        self.critical_rows = alerts
        self.critical_table.setRowCount(len(alerts))
        for row, item in enumerate(alerts):
            values = [
                item.get("patient_name") or "",
                item.get("item_name") or "",
                item.get("result_display") or "—",
                str(item.get("reported_at") or "")[:16].replace("T", " "),
                f"{item.get('critical_age_minutes') or 0} 分钟"
                + ("（超时）" if item.get("critical_overdue") else ""),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 0:
                    cell.setData(Qt.UserRole, item["id"])
                if item.get("critical_overdue"):
                    cell.setForeground(Qt.red)
                self.critical_table.setItem(row, col, cell)
        if alerts:
            self.critical_msg.setText(
                f"待确认 {len(alerts)} 条；超时 {sum(1 for x in alerts if x.get('critical_overdue'))} 条"
            )
            self.critical_msg.setStyleSheet("color:#b91c1c;font-weight:bold")
        else:
            self.critical_msg.setText("暂无未确认危急值")
            self.critical_msg.setStyleSheet("")

    def _select_critical(self, row: int, _col: int) -> None:
        if 0 <= row < len(getattr(self, "critical_rows", [])):
            item = self.critical_rows[row]
            self.critical_note.setText(
                f"{item.get('patient_name')} {item.get('item_name')} {item.get('result_display')}"
            )

    def _ack_critical(self) -> None:
        row = self.critical_table.currentRow()
        if row < 0:
            self.critical_msg.setText("请先选择一条危急值")
            return
        cell = self.critical_table.item(row, 0)
        request_id = cell.data(Qt.UserRole) if cell else None
        if not request_id:
            return
        try:
            self.api.ack_critical_lab(request_id, self.critical_note.text().strip())
        except ApiError as e:
            self.critical_msg.setText(f"确认失败（{e.status_code}）：{e.detail}")
            return
        self.critical_msg.setText("危急值已确认")
        self._load_critical_alerts()

    def _select_workbench(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self.workbench_rows)):
            return
        item = self.workbench_rows[row]
        self.wb_current = item
        self.banner.set_patient(
            {
                "id": item.get("patient_id"),
                "patient_no": item.get("patient_no"),
                "name": item.get("patient_name"),
                "gender": item.get("gender"),
                "age": item.get("age"),
                "allergy_label": item.get("allergy_label"),
            },
            item.get("encounter_id"),
            "已接诊" if item.get("encounter_id") else "待接诊",
        )
        gender = {"male": "男", "female": "女"}.get(item.get("gender"), "不详")
        age = item.get("age")
        allergy = item.get("allergy_label") or "不详"
        self.wb_patient.setText(
            f"{item['patient_name']} · {gender}/{age if age is not None else '—'}岁 · "
            f"过敏：{allergy} · 分诊 {item.get('triage_level') or '—'} 级 · "
            f"{item.get('vital_summary') or '未测生命体征'} · "
            f"挂号 {item['registration_id']} · 就诊 {item.get('encounter_id') or '未接诊'}"
        )
        if item.get("isolation"):
            self.wb_patient.setText(self.wb_patient.text() + " · 隔离提示")
            self.wb_patient.setStyleSheet("color:#b91c1c;font-weight:bold")
        elif item.get("allergy_label") not in (None, "", "无过敏史", "过敏史不详"):
            self.wb_patient.setStyleSheet("color:#b91c1c;font-weight:bold")
        else:
            self.wb_patient.setStyleSheet("")
        self.wb_diagnosis.setText(item.get("diagnosis") or "")
        code_index = self.wb_diagnosis_code.findData(item.get("diagnosis_code") or "")
        if code_index >= 0:
            self.wb_diagnosis_code.blockSignals(True)
            self.wb_diagnosis_code.setCurrentIndex(code_index)
            self.wb_diagnosis_code.blockSignals(False)
        self.wb_start.setEnabled(not item.get("encounter_id"))
        if item.get("encounter_id"):
            self._set_encounter_everywhere(item["encounter_id"])
            self._load_workbench_summary(item["encounter_id"])
        else:
            self._set_encounter_everywhere(None)
            self.wb_fee_table.setRowCount(0)
            self.wb_summary.setText("尚未接诊，填写诊断后点「开始接诊」")

    def _load_workbench_summary(self, encounter_id: int) -> None:
        try:
            summary = self.api.encounter_summary(encounter_id)
        except ApiError as e:
            self.wb_summary.setText(f"加载就诊摘要失败（{e.status_code}）：{e.detail}")
            return
        self.wb_summary_data = summary
        self.wb_summary.setText(
            f"诊断：{summary.get('diagnosis_code') or ''} {summary['diagnosis'] or '—'}　状态："
            f"{zh('encounter_status', summary['status'])}　"
            f"病历：{'已签名' if summary['record_signed'] else '未签名'}　"
            f"费用：{summary['total_amount']:.2f} 元（待缴 {summary['pending_amount']:.2f}）　"
            f"处方 {summary['prescription_count']} / 检验 {summary['lab_count']} / 治疗 {summary['treatment_count']}"
        )
        charges = summary.get("charges") or []
        self.wb_fee_table.setRowCount(len(charges))
        for row, charge in enumerate(charges):
            values = [
                charge["item_name"],
                str(charge["quantity"]),
                f"{charge['amount']:.2f}",
                zh("charge_status", charge["status"]),
            ]
            for col, value in enumerate(values):
                self.wb_fee_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.reg_id.setValue(summary["registration_id"])
        self.mr_encounter_id.setValue(encounter_id)
        self.rx_encounter_id.setValue(encounter_id)
        self.exam_encounter_id.setValue(encounter_id)
        self.treat_encounter_id.setValue(encounter_id)

    def _start_workbench(self) -> None:
        item = getattr(self, "wb_current", None)
        if not item:
            self.wb_summary.setText("请先选择患者")
            return
        try:
            encounter = self.api.create_encounter(
                item["registration_id"],
                self.wb_diagnosis.text().strip(),
                self.wb_diagnosis_code.currentData() or "",
            )
        except ApiError as e:
            self.wb_summary.setText(f"接诊失败（{e.status_code}）：{e.detail}")
            return
        self._load_workbench()
        for row, candidate in enumerate(self.workbench_rows):
            if candidate["registration_id"] == item["registration_id"]:
                self.wb_table.selectRow(row)
                self._select_workbench(row, 0)
                break
        self.wb_summary.setText(f"接诊成功：就诊 ID {encounter['id']}")
        self._set_encounter_everywhere(encounter["id"])
        self.banner.set_patient(
            {
                "id": item.get("patient_id"),
                "patient_no": item.get("patient_no"),
                "name": item.get("patient_name"),
                "gender": item.get("gender"),
                "age": item.get("age"),
                "allergy_label": item.get("allergy_label"),
            },
            encounter["id"],
            "已接诊",
        )

    def _switch_tab(self, text: str) -> None:
        for index in range(self.tabs.count()):
            if text in self.tabs.tabText(index):
                self.tabs.setCurrentIndex(index)
                return

    def _set_encounter_everywhere(self, encounter_id: int | None) -> None:
        for attr in (
            "mr_encounter_id",
            "rx_encounter_id",
            "exam_encounter_id",
            "treat_encounter_id",
        ):
            spin = getattr(self, attr, None)
            if spin is not None:
                spin.setValue(int(encounter_id or 0))

    def _wb_record(self) -> None:
        self._switch_tab("病历")
        if hasattr(self, "mr_encounter_id") and self.wb_current:
            self._set_encounter_everywhere(self.wb_current.get("encounter_id"))
            self._load_record()

    def _wb_prescribe(self) -> None:
        self._switch_tab("开方")
        if self.wb_current:
            self._set_encounter_everywhere(self.wb_current.get("encounter_id"))
            self._load_drugs()

    def _wb_exam(self) -> None:
        self._switch_tab("检验")
        if self.wb_current:
            self._set_encounter_everywhere(self.wb_current.get("encounter_id"))

    def _wb_treat(self) -> None:
        self._switch_tab("治疗")
        if self.wb_current:
            self._set_encounter_everywhere(self.wb_current.get("encounter_id"))
            self._load_treatment_items()

    def _wb_history(self) -> None:
        self._switch_tab("历史诊疗")
        if self.wb_current and self.wb_current.get("patient_id"):
            self._load_history(self.wb_current["patient_id"])

    # ---------- 挂号（医生站现场挂号） ----------
    def _build_register_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        search_box = QGroupBox("查询患者（未建档请先到收费员工作站建档）")
        search_layout = QVBoxLayout(search_box)
        row = QHBoxLayout()
        self.reg_patient_name = QLineEdit()
        self.reg_patient_name.setPlaceholderText("姓名（可空）")
        self.reg_patient_id_number = QLineEdit()
        self.reg_patient_id_number.setPlaceholderText("身份证号（可空）")
        search = QPushButton("查询患者")
        search.clicked.connect(self._search_registration_patients)
        row.addWidget(QLabel("姓名"))
        row.addWidget(self.reg_patient_name)
        row.addWidget(QLabel("身份证号"))
        row.addWidget(self.reg_patient_id_number)
        row.addWidget(search)
        search_layout.addLayout(row)

        self.reg_patient_table = QTableWidget(0, 4)
        self.reg_patient_table.setHorizontalHeaderLabels(["患者 ID", "姓名", "身份证号", "电话"])
        search_layout.addWidget(self.reg_patient_table)
        layout.addWidget(search_box)

        box = QGroupBox("现场挂号")
        form = QFormLayout(box)
        self.reg_patient_id = QLineEdit()
        self.reg_patient_id.setReadOnly(True)
        self.reg_patient_id.setPlaceholderText("在上表选择患者")
        self.reg_doctor = QComboBox()
        load_doctors = QPushButton("刷新医生")
        load_doctors.clicked.connect(self._load_registration_doctors)
        doctor_row = QHBoxLayout()
        doctor_row.addWidget(self.reg_doctor)
        doctor_row.addWidget(load_doctors)
        self.reg_msg = QLabel("")
        self.reg_msg.setWordWrap(True)
        submit = QPushButton("挂号")
        submit.clicked.connect(self._create_registration)
        form.addRow("患者 ID", self.reg_patient_id)
        form.addRow("医生", doctor_row)
        form.addRow("", submit)
        form.addRow("", self.reg_msg)
        layout.addWidget(box)
        layout.addStretch(1)

        self.reg_patient_table.cellClicked.connect(self._select_registration_patient)
        return page

    def _search_registration_patients(self) -> None:
        try:
            patients = self.api.list_patients(
                name=self.reg_patient_name.text().strip() or None,
                id_number=self.reg_patient_id_number.text().strip() or None,
            )
        except ApiError as e:
            self.reg_msg.setText(f"查询患者失败（{e.status_code}）：{e.detail}")
            return
        self.reg_patient_table.setRowCount(len(patients))
        for row, patient in enumerate(patients):
            values = [
                str(patient["id"]),
                patient["name"],
                patient.get("id_number", ""),
                patient.get("phone", ""),
            ]
            for col, value in enumerate(values):
                self.reg_patient_table.setItem(row, col, QTableWidgetItem(value))
        self.reg_msg.setText(f"共 {len(patients)} 位患者")

    def _select_registration_patient(self, row: int, _col: int) -> None:
        item = self.reg_patient_table.item(row, 0)
        if item:
            self.reg_patient_id.setText(item.text())

    def _load_registration_doctors(self) -> None:
        try:
            doctors = self.api.list_doctors()
        except ApiError as e:
            self.reg_msg.setText(f"加载医生失败（{e.status_code}）：{e.detail}")
            return
        self.reg_doctor.clear()
        for doctor in doctors:
            self.reg_doctor.addItem(
                f"{doctor['name']}（科室 {doctor.get('department_id')}）", doctor["id"]
            )
        self.reg_msg.setText(f"医生 {len(doctors)} 位")

    def _create_registration(self) -> None:
        patient_id = self.reg_patient_id.text().strip()
        doctor_id = self.reg_doctor.currentData()
        if not patient_id:
            self.reg_msg.setText("请先在上表选择患者")
            return
        if not doctor_id:
            self.reg_msg.setText("请先刷新并选择医生")
            return
        try:
            registration = self.api.create_registration(int(patient_id), doctor_id)
        except ApiError as e:
            self.reg_msg.setText(f"挂号失败（{e.status_code}）：{e.detail}")
            return
        self.reg_msg.setText(
            f"挂号成功：挂号 ID {registration['id']}，状态 "
            f"{zh('registration_status', registration['status'])}，可到「接诊」页开始接诊"
        )
        if hasattr(self, "reg_id"):
            self.reg_id.setValue(registration["id"])
        self._load_pending_registrations()

    # ---------- 接诊 ----------
    def _build_reception_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        refresh = QPushButton("刷新待接诊挂号")
        refresh.clicked.connect(self._load_pending_registrations)
        row.addWidget(refresh)
        layout.addLayout(row)

        self.reg_table = QTableWidget(0, 4)
        self.reg_table.setHorizontalHeaderLabels(["挂号 ID", "患者 ID", "医生 ID", "状态"])
        layout.addWidget(self.reg_table)

        box = QGroupBox("接诊")
        form = QFormLayout(box)
        self.reg_id = QSpinBox()
        self.reg_id.setRange(1, 10_000_000)
        self.rec_diagnosis_code = QComboBox()
        self.rec_diagnosis_code.addItem("诊断编码（可选）", "")
        self.rec_diagnosis_code.currentIndexChanged.connect(self._diagnosis_selected)
        self.diagnosis = QLineEdit()
        self.diagnosis.setPlaceholderText("诊断，如：上呼吸道感染")
        start = QPushButton("开始接诊")
        start.clicked.connect(self._start_encounter)
        form.addRow("挂号 ID", self.reg_id)
        form.addRow("诊断编码", self.rec_diagnosis_code)
        form.addRow("诊断", self.diagnosis)
        form.addRow("", start)
        layout.addWidget(box)

        self.reception_msg = QLabel("")
        self.reception_msg.setWordWrap(True)
        layout.addWidget(self.reception_msg)
        layout.addStretch(1)
        return page

    def _load_pending_registrations(self) -> None:
        try:
            rows = self.api.list_registrations(status="registered")
        except ApiError as e:
            self.reception_msg.setText(f"加载失败：{e.detail}")
            return
        self.reg_table.setRowCount(len(rows))
        for index, reg in enumerate(rows):
            self.reg_table.setItem(index, 0, QTableWidgetItem(str(reg["id"])))
            self.reg_table.setItem(index, 1, QTableWidgetItem(str(reg["patient_id"])))
            self.reg_table.setItem(index, 2, QTableWidgetItem(str(reg["doctor_id"])))
            self.reg_table.setItem(index, 3, QTableWidgetItem(zh('registration_status', reg["status"])))
        self.reg_table.cellClicked.connect(
            lambda row, _col: self.reg_id.setValue(
                int(self.reg_table.item(row, 0).text())
            )
        )

    def _start_encounter(self) -> None:
        try:
            encounter = self.api.create_encounter(
                self.reg_id.value(),
                self.diagnosis.text().strip(),
                self.rec_diagnosis_code.currentData() or "",
            )
        except ApiError as e:
            self.reception_msg.setText(f"接诊失败（{e.status_code}）：{e.detail}")
            return
        self.reception_msg.setText(
            f"接诊成功：就诊 ID {encounter['id']}，诊断「{encounter['diagnosis']}」"
        )

    # ---------- 病历 ----------
    def _build_record_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        top = QHBoxLayout()
        self.mr_encounter_id = QSpinBox()
        self.mr_encounter_id.setRange(0, 10_000_000)
        self.mr_encounter_id.setSpecialValueText("未接诊")
        self.mr_encounter_id.setReadOnly(True)
        self.mr_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        load = QPushButton("载入病历")
        load.clicked.connect(self._load_record)
        top.addWidget(QLabel("就诊 ID"))
        top.addWidget(self.mr_encounter_id)
        top.addWidget(load)
        layout.addLayout(top)

        self.record_edits: dict[str, QTextEdit] = {}
        for key, label, _limit in _RECORD_FIELDS:
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            edit = QTextEdit()
            edit.setFixedHeight(70)
            self.record_edits[key] = edit
            box_layout.addWidget(edit)
            layout.addWidget(box)

        buttons = QHBoxLayout()
        save = QPushButton("保存 / 更新")
        save.clicked.connect(self._save_record)
        sign = QPushButton("签名锁定")
        sign.clicked.connect(self._sign_record)
        quality = QPushButton("质控评分")
        quality.clicked.connect(self._check_quality)
        buttons.addWidget(save)
        buttons.addWidget(sign)
        buttons.addWidget(quality)
        layout.addLayout(buttons)

        self.record_msg = QLabel("")
        self.record_msg.setWordWrap(True)
        layout.addWidget(self.record_msg)
        layout.addStretch(1)
        return page

    def _load_record(self) -> None:
        try:
            record = self.api.get_medical_record(self.mr_encounter_id.value())
        except ApiError as e:
            self.record_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        for key, _label, _limit in _RECORD_FIELDS:
            self.record_edits[key].setPlainText(record.get(key) or "")
        self.record_msg.setText(
            f"病历已载入（书写：{record.get('written_by') or '—'}，"
            f"签名：{record.get('signed_by') or '未签名'}）"
        )

    def _record_payload(self) -> dict:
        return {
            key: self.record_edits[key].toPlainText().strip()
            for key, _label, limit in _RECORD_FIELDS
            if len(self.record_edits[key].toPlainText().strip()) <= limit
        }

    def _save_record(self) -> None:
        encounter_id = self.mr_encounter_id.value()
        payload = self._record_payload()
        try:
            try:
                record = self.api.update_medical_record(encounter_id, payload)
                action = "更新"
            except ApiError as e:
                # 新病历：服务端 404（历史版本返回 400 +「还没有病历」）时改为创建
                if e.status_code == 404 or (
                    e.status_code == 400 and "还没有病历" in (e.detail or "")
                ):
                    record = self.api.create_medical_record(encounter_id, payload)
                    action = "创建"
                else:
                    raise
        except ApiError as e:
            self.record_msg.setText(f"保存失败（{e.status_code}）：{e.detail}")
            return
        self.record_msg.setText(f"病历已{action}（{record.get('id')}）")

    def _sign_record(self) -> None:
        try:
            record = self.api.sign_medical_record(self.mr_encounter_id.value())
        except ApiError as e:
            self.record_msg.setText(f"签名失败（{e.status_code}）：{e.detail}")
            return
        self.record_msg.setText(f"已签名锁定：{record.get('signed_by')}")

    def _check_quality(self) -> None:
        try:
            quality = self.api.medical_record_quality(self.mr_encounter_id.value())
        except ApiError as e:
            self.record_msg.setText(f"质控失败（{e.status_code}）：{e.detail}")
            return
        missing = "、".join(quality.get("missing_fields") or []) or "无"
        self.record_msg.setText(
            f"质控得分 {quality['score']}（{'通过' if quality['passed'] else '不通过'}），缺项：{missing}"
        )

    # ---------- 历史诊疗 ----------
    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        self.history_name = QLineEdit()
        self.history_name.setPlaceholderText("患者姓名（可空）")
        self.history_id_number = QLineEdit()
        self.history_id_number.setPlaceholderText("身份证号（可空）")
        search = QPushButton("查询患者")
        search.clicked.connect(self._search_history_patients)
        row.addWidget(QLabel("姓名"))
        row.addWidget(self.history_name)
        row.addWidget(QLabel("身份证号"))
        row.addWidget(self.history_id_number)
        row.addWidget(search)
        layout.addLayout(row)

        self.history_patient_table = QTableWidget(0, 3)
        self.history_patient_table.setHorizontalHeaderLabels(["患者 ID", "姓名", "身份证号"])
        self.history_patient_table.setMaximumHeight(130)
        self.history_patient_table.cellClicked.connect(self._select_history_patient)
        layout.addWidget(self.history_patient_table)

        self.history_patient_label = QLabel("请选择患者查看历史诊疗")
        self.history_patient_label.setStyleSheet("font-weight:bold;color:#0f172a")
        layout.addWidget(self.history_patient_label)
        self.history_msg = QLabel("")
        self.history_msg.setWordWrap(True)
        layout.addWidget(self.history_msg)

        splitter = QSplitter(Qt.Vertical)
        self.history_enc_table = QTableWidget(0, 5)
        self.history_enc_table.setHorizontalHeaderLabels(
            ["就诊 ID", "就诊时间", "诊断", "医生", "状态"]
        )
        self.history_enc_table.cellClicked.connect(self._history_select)
        splitter.addWidget(self.history_enc_table)

        detail = QTabWidget()
        self.history_detail_tabs = detail
        self.history_record = QTextEdit()
        self.history_record.setReadOnly(True)
        detail.addTab(self.history_record, "病历")
        self.history_rx_table = self._history_table(["药品", "数量", "用法", "金额"])
        detail.addTab(self.history_rx_table, "处方")
        self.history_lab_table = self._history_table(
            ["项目", "状态", "结果", "参考范围", "异常", "报告时间"]
        )
        detail.addTab(self.history_lab_table, "检验")
        self.history_treat_table = self._history_table(["项目", "数量", "状态", "执行人"])
        detail.addTab(self.history_treat_table, "治疗")
        self.history_charge_table = self._history_table(
            ["项目", "数量", "金额", "状态"]
        )
        detail.addTab(self.history_charge_table, "收费")
        self.history_pay_table = self._history_table(
            ["支付单", "金额", "医保", "自费", "状态"]
        )
        detail.addTab(self.history_pay_table, "支付")
        splitter.addWidget(detail)
        splitter.setSizes([150, 420])
        layout.addWidget(splitter, 1)
        return page

    @staticmethod
    def _history_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        return table

    def _search_history_patients(self) -> None:
        try:
            patients = self.api.list_patients(
                name=self.history_name.text().strip() or None,
                id_number=self.history_id_number.text().strip() or None,
            )
        except ApiError as e:
            self.history_msg.setText(f"查询失败（{e.status_code}）：{e.detail}")
            return
        self.history_patient_table.setRowCount(len(patients))
        for row, patient in enumerate(patients):
            values = [str(patient["id"]), patient["name"], patient.get("id_number", "")]
            for col, value in enumerate(values):
                self.history_patient_table.setItem(row, col, QTableWidgetItem(value))
        self.history_msg.setText(f"共 {len(patients)} 位患者，点击选择查看历史")

    def _select_history_patient(self, row: int, _col: int) -> None:
        item = self.history_patient_table.item(row, 0)
        if item:
            self._load_history(int(item.text()))

    def _load_history(self, patient_id: int) -> None:
        try:
            data = self.api.get_patient_history(patient_id)
        except ApiError as e:
            self.history_msg.setText(f"加载历史失败（{e.status_code}）：{e.detail}")
            return
        self.history_data = data
        patient = data["patient"]
        self.history_patient_label.setText(
            f"患者：{patient['name']}（ID {patient['id']}）  "
            f"历史就诊 {len(data['encounters'])} 次"
        )
        self.history_msg.setText("点击就诊行查看该次病历、处方、检验、治疗、收费")
        table = self.history_enc_table
        table.setRowCount(len(data["encounters"]))
        for row, encounter in enumerate(data["encounters"]):
            values = [
                str(encounter["id"]),
                str(encounter["visited_at"])[:16].replace("T", " "),
                f"{encounter.get('diagnosis_code') or ''} {encounter['diagnosis']}".strip(),
                encounter["doctor_name"],
                zh("encounter_status", encounter["status"]),
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
        if data["encounters"]:
            table.selectRow(0)
            self._render_history(data["encounters"][0])
        else:
            self.history_record.setPlainText("该患者暂无就诊记录")
            for widget in (
                self.history_rx_table,
                self.history_lab_table,
                self.history_treat_table,
                self.history_charge_table,
                self.history_pay_table,
            ):
                widget.setRowCount(0)

    def _history_select(self, row: int, _col: int) -> None:
        encounters = getattr(self, "history_data", {}).get("encounters", [])
        if 0 <= row < len(encounters):
            self._render_history(encounters[row])

    def _render_history(self, encounter: dict) -> None:
        record = encounter.get("medical_record")
        if record:
            self.history_record.setPlainText(
                "\n".join(
                    [
                        f"主诉：{record.get('chief_complaint') or '—'}",
                        f"现病史：{record.get('present_illness') or '—'}",
                        f"既往史：{record.get('past_history') or '—'}",
                        f"体格检查：{record.get('physical_exam') or '—'}",
                        f"处理意见：{record.get('treatment_advice') or '—'}",
                        f"签名：{record.get('signed_by') or '未签名'}"
                        f"（{str(record.get('signed_at') or '')[:16]}）",
                    ]
                )
            )
        else:
            self.history_record.setPlainText("本次就诊暂无病历")

        self._fill_history_table(
            self.history_rx_table,
            [
                [
                    item["drug_name"],
                    str(item["quantity"]),
                    f"{item['dosage']} {item['frequency']} {item['route']}".strip()
                    or "—",
                    f"{item['amount']:.2f}",
                ]
                for item in encounter["prescriptions"]
            ],
        )
        self._fill_history_table(
            self.history_lab_table,
            [
                [
                    item["item_name"],
                    zh("lab_status", item["status"]),
                    (
                        f"{item['result_value']:g} {item.get('result_unit') or ''}".strip()
                        if item.get("result_value") is not None
                        else item.get("result") or "—"
                    ),
                    (
                        f"{item['reference_low']:g}–{item['reference_high']:g}"
                        if item.get("reference_low") is not None
                        and item.get("reference_high") is not None
                        else "—"
                    ),
                    {"H": "↑ 偏高", "L": "↓ 偏低", "N": "正常"}.get(
                        item.get("abnormal_flag") or "", "—"
                    ),
                    str(item.get("reported_at") or "")[:16].replace("T", " "),
                ]
                for item in encounter["lab_requests"]
            ],
        )
        self._fill_history_table(
            self.history_treat_table,
            [
                [
                    item["item_name"],
                    str(item["quantity"]),
                    zh("treatment_status", item["status"]),
                    item.get("executed_by") or "—",
                ]
                for item in encounter["treatments"]
            ],
        )
        self._fill_history_table(
            self.history_charge_table,
            [
                [
                    item["item_name"],
                    str(item["quantity"]),
                    f"{item['amount']:.2f}",
                    zh("charge_status", item["status"]),
                ]
                for item in encounter["charges"]
            ],
        )
        self._fill_history_table(
            self.history_pay_table,
            [
                [
                    str(item["id"]),
                    f"{item['amount']:.2f}",
                    f"{item['insurance_amount']:.2f}",
                    f"{item['self_pay_amount']:.2f}",
                    zh("payment_status", item["status"]),
                ]
                for item in encounter["payments"]
            ],
        )

    @staticmethod
    def _fill_history_table(table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for col, value in enumerate(values):
                table.setItem(row_index, col, QTableWidgetItem(str(value)))

    # ---------- 开方 ----------
    def _build_prescription_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        top = QHBoxLayout()
        self.rx_encounter_id = QSpinBox()
        self.rx_encounter_id.setRange(0, 10_000_000)
        self.rx_encounter_id.setSpecialValueText("未接诊")
        self.rx_encounter_id.setReadOnly(True)
        self.rx_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        load = QPushButton("刷新药品目录")
        load.clicked.connect(self._load_drugs)
        top.addWidget(QLabel("就诊 ID"))
        top.addWidget(self.rx_encounter_id)
        top.addWidget(load)
        self.rx_search = QLineEdit()
        self.rx_search.setPlaceholderText("搜索药名/规格（输入即筛选）")
        self.rx_search.setClearButtonEnabled(True)
        self.rx_search.textChanged.connect(self._filter_drugs)
        top.addWidget(self.rx_search, 1)
        layout.addLayout(top)

        self.drug_table = QTableWidget(0, 8)
        self.drug_table.setHorizontalHeaderLabels(
            ["ID", "药品", "规格", "单价", "库存", "自费约", "医保比例", "医保类别"]
        )
        if not self.insurance_enabled:
            self.drug_table.setColumnHidden(6, True)
            self.drug_table.setColumnHidden(7, True)
        self.drug_table.cellClicked.connect(self._pick_drug_row)
        self.drug_table.cellDoubleClicked.connect(self._pick_drug_row)
        layout.addWidget(self.drug_table)

        box = QGroupBox("开立处方")
        form = QFormLayout(box)
        self.rx_drug_id = QLineEdit()
        self.rx_drug_id.setReadOnly(True)
        self.rx_quantity = QSpinBox()
        self.rx_quantity.setRange(1, 100)
        self.rx_dosage = QLineEdit()
        self.rx_dosage.setPlaceholderText("如 0.5g")
        self.rx_frequency = QLineEdit()
        self.rx_frequency.setPlaceholderText("如 bid / tid")
        self.rx_frequency.setCompleter(
            QCompleter(["qd", "bid", "tid", "qid", "q8h", "q12h", "prn", "st"])
        )
        self.rx_route = QLineEdit()
        self.rx_route.setPlaceholderText("如 口服 / 静滴")
        self.rx_route.setCompleter(
            QCompleter(["口服", "静滴", "肌注", "皮下", "外用", "舌下", "雾化", "滴眼"])
        )
        self.rx_days = QSpinBox()
        self.rx_days.setRange(1, 365)
        self.rx_days.setValue(3)
        submit = QPushButton("开方")
        submit.clicked.connect(self._add_prescription)
        form.addRow("药品 ID", self.rx_drug_id)
        form.addRow("数量", self.rx_quantity)
        form.addRow("每次剂量", self.rx_dosage)
        form.addRow("频次", self.rx_frequency)
        form.addRow("途径", self.rx_route)
        form.addRow("天数", self.rx_days)
        form.addRow("", submit)
        layout.addWidget(box)

        self.rx_msg = QLabel("")
        self.rx_msg.setWordWrap(True)
        layout.addWidget(self.rx_msg)

        self.rx_table = QTableWidget(0, 5)
        self.rx_table.setHorizontalHeaderLabels(["药品", "数量", "单价", "用法", "金额"])
        layout.addWidget(self.rx_table)
        return page

    def _load_drugs(self) -> None:
        try:
            drugs = self.api.list_drugs()
            stocks = self.api.list_stocks()
        except ApiError as e:
            self.rx_msg.setText(f"加载药品失败：{e.detail}")
            return
        stock_by_drug: dict[int, int] = {}
        for stock in stocks:
            stock_by_drug[stock["drug_id"]] = (
                stock_by_drug.get(stock["drug_id"], 0) + stock["quantity"]
            )
        self.drug_rows = []
        for drug in drugs:
            self.drug_rows.append(
                {
                    **drug,
                    "stock": stock_by_drug.get(drug["id"], 0),
                    "self_pay": round(
                        drug["base_price"]
                        * (1 - drug["insurance_ratio"])
                        if self.insurance_enabled
                        else drug["base_price"],
                        2,
                    ),
                }
            )
        self._filter_drugs()

    def _filter_drugs(self) -> None:
        term = self.rx_search.text().strip().lower() if hasattr(self, "rx_search") else ""
        rows = getattr(self, "drug_rows", [])
        if term:
            rows = [
                drug
                for drug in rows
                if term in str(drug.get("name", "")).lower()
                or term in str(drug.get("spec", "")).lower()
            ]
        self.drug_table.setRowCount(len(rows))
        for row, drug in enumerate(rows):
            category = drug.get("insurance_category") or ""
            status = drug.get("insurance_match_status") or "unmatched"
            tag = f"{category}类" if category else ("歧义" if status == "ambiguous" else "未对码")
            values = [
                str(drug["id"]),
                drug["name"],
                drug.get("spec") or "",
                f"{drug['base_price']:.2f}",
                str(drug.get("stock", 0)),
                f"{drug.get('self_pay', drug['base_price']):.2f}",
                str(drug["insurance_ratio"]),
                tag,
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 4 and drug.get("stock", 0) <= 0:
                    cell.setForeground(Qt.red)
                self.drug_table.setItem(row, col, cell)
        self.rx_msg.setText(f"药品 {len(rows)} 种" + (f"（筛选：{term}）" if term else ""))

    def _pick_drug_row(self, row: int, _col: int) -> None:
        cell = self.drug_table.item(row, 0)
        if not cell:
            return
        self.rx_drug_id.setText(cell.text())
        if not self.rx_frequency.text().strip():
            self.rx_frequency.setText("bid")
        if not self.rx_route.text().strip():
            self.rx_route.setText("口服")

    def _add_prescription(self) -> None:
        drug_id = self.rx_drug_id.text().strip()
        if not drug_id:
            self.rx_msg.setText("请先在药品目录中点击选择药品")
            return
        payload = {
            "drug_id": int(drug_id),
            "quantity": self.rx_quantity.value(),
            "dosage": self.rx_dosage.text().strip(),
            "frequency": self.rx_frequency.text().strip(),
            "route": self.rx_route.text().strip(),
            "days": self.rx_days.value(),
        }
        try:
            item = self.api.add_prescription(self.rx_encounter_id.value(), payload)
        except ApiError as e:
            if e.status_code == 400 and "过敏" in (e.detail or ""):
                reason, ok = QInputDialog.getText(
                    self,
                    "过敏史冲突",
                    f"{e.detail}\n\n如确认可继续使用，请填写 override 理由：",
                )
                if not ok or not reason.strip():
                    self.rx_msg.setText(f"已取消开方：{e.detail}")
                    return
                payload["allergy_override_reason"] = reason.strip()
                try:
                    item = self.api.add_prescription(
                        self.rx_encounter_id.value(), payload
                    )
                except ApiError as retry_error:
                    self.rx_msg.setText(
                        f"开方失败（{retry_error.status_code}）：{retry_error.detail}"
                    )
                    return
            else:
                self.rx_msg.setText(f"开方失败（{e.status_code}）：{e.detail}")
                return
        warning = f"；医保提醒：{item['insurance_warning']}" if self.insurance_enabled and item.get("insurance_warning") else ""
        allergy = f"；过敏冲突已 override：{item['allergy_warning']}" if item.get("allergy_warning") else ""
        self.rx_msg.setText(
            f"开方成功：{item['drug_name']} × {item['quantity']}{warning}{allergy}"
        )
        self._refresh_prescriptions()

    def _refresh_prescriptions(self) -> None:
        try:
            items = self.api.list_prescriptions(self.rx_encounter_id.value())
        except ApiError:
            return
        self.rx_table.setRowCount(len(items))
        for row, item in enumerate(items):
            usage = " ".join(
                part
                for part in (
                    item.get("dosage"),
                    item.get("frequency"),
                    item.get("route"),
                    f"{item.get('days')}天" if item.get("days") else "",
                )
                if part
            )
            self.rx_table.setItem(row, 0, QTableWidgetItem(item["drug_name"]))
            self.rx_table.setItem(row, 1, QTableWidgetItem(str(item["quantity"])))
            self.rx_table.setItem(row, 2, QTableWidgetItem(f"{item['unit_price']:.2f}"))
            self.rx_table.setItem(row, 3, QTableWidgetItem(usage or "—"))
            self.rx_table.setItem(
                row, 4, QTableWidgetItem(f"{item['quantity'] * item['unit_price']:.2f}")
            )

    # ---------- 检验 / 检查 ----------
    def _build_exam_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.exam_encounter_id = QSpinBox()
        self.exam_encounter_id.setRange(0, 10_000_000)
        self.exam_encounter_id.setSpecialValueText("未接诊")
        self.exam_encounter_id.setReadOnly(True)
        self.exam_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        row = QHBoxLayout()
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.exam_encounter_id)
        layout.addLayout(row)

        lab_box = QGroupBox("检验开单")
        lab_layout = QHBoxLayout(lab_box)
        self.lab_combo = QComboBox()
        load_lab = QPushButton("刷新检验项目")
        load_lab.clicked.connect(self._load_lab_items)
        submit_lab = QPushButton("开检验单")
        submit_lab.clicked.connect(self._create_lab)
        lab_layout.addWidget(self.lab_combo)
        lab_layout.addWidget(load_lab)
        lab_layout.addWidget(submit_lab)
        layout.addWidget(lab_box)

        img_box = QGroupBox("检查开单")
        img_layout = QHBoxLayout(img_box)
        self.img_combo = QComboBox()
        load_img = QPushButton("刷新检查项目")
        load_img.clicked.connect(self._load_imaging_items)
        submit_img = QPushButton("开检查单")
        submit_img.clicked.connect(self._create_imaging)
        img_layout.addWidget(self.img_combo)
        img_layout.addWidget(load_img)
        img_layout.addWidget(submit_img)
        layout.addWidget(img_box)

        self.exam_msg = QLabel("")
        self.exam_msg.setWordWrap(True)
        layout.addWidget(self.exam_msg)
        layout.addStretch(1)
        return page

    def _load_lab_items(self) -> None:
        try:
            items = self.api.list_lab_items()
        except ApiError as e:
            self.exam_msg.setText(f"加载检验项目失败：{e.detail}")
            return
        self.lab_combo.clear()
        for item in items:
            self.lab_combo.addItem(f"{item['name']}（{item['price']:.2f} 元）", item["id"])

    def _load_imaging_items(self) -> None:
        try:
            items = self.api.list_imaging_items()
        except ApiError as e:
            self.exam_msg.setText(f"加载检查项目失败：{e.detail}")
            return
        self.img_combo.clear()
        for item in items:
            self.img_combo.addItem(f"{item['name']}（{item['price']:.2f} 元）", item["id"])

    def _create_lab(self) -> None:
        item_id = self.lab_combo.currentData()
        if not item_id:
            self.exam_msg.setText("请先刷新并选择检验项目")
            return
        try:
            request = self.api.create_lab_request(self.exam_encounter_id.value(), item_id)
        except ApiError as e:
            self.exam_msg.setText(f"开单失败（{e.status_code}）：{e.detail}")
            return
        self.exam_msg.setText(f"检验已开单：{request['item_name']}（{request['id']}）")

    def _create_imaging(self) -> None:
        item_id = self.img_combo.currentData()
        if not item_id:
            self.exam_msg.setText("请先刷新并选择检查项目")
            return
        try:
            request = self.api.create_imaging_request(
                self.exam_encounter_id.value(), item_id
            )
        except ApiError as e:
            self.exam_msg.setText(f"开单失败（{e.status_code}）：{e.detail}")
            return
        self.exam_msg.setText(f"检查已开单：{request['item_name']}（{request['id']}）")

    # ---------- 治疗 ----------
    def _build_treatment_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("开治疗单")
        form = QFormLayout(box)
        self.treat_encounter_id = QSpinBox()
        self.treat_encounter_id.setRange(0, 10_000_000)
        self.treat_encounter_id.setSpecialValueText("未接诊")
        self.treat_encounter_id.setReadOnly(True)
        self.treat_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.treat_combo = QComboBox()
        self.treat_quantity = QSpinBox()
        self.treat_quantity.setRange(1, 100)
        self.treat_note = QLineEdit()
        self.treat_note.setPlaceholderText("如：头孢曲松 2g 静滴")
        load = QPushButton("刷新治疗项目")
        load.clicked.connect(self._load_treatment_items)
        submit = QPushButton("开治疗单")
        submit.clicked.connect(self._create_treatment)
        form.addRow("就诊 ID", self.treat_encounter_id)
        form.addRow("治疗项目", self.treat_combo)
        form.addRow("数量", self.treat_quantity)
        form.addRow("备注", self.treat_note)
        form.addRow("", load)
        form.addRow("", submit)
        layout.addWidget(box)

        self.treat_msg = QLabel("")
        self.treat_msg.setWordWrap(True)
        layout.addWidget(self.treat_msg)
        layout.addStretch(1)
        return page

    def _load_treatment_items(self) -> None:
        try:
            items = self.api.list_charge_items("treatment")
        except ApiError as e:
            self.treat_msg.setText(f"加载治疗项目失败：{e.detail}")
            return
        self.treat_combo.clear()
        for item in items:
            self.treat_combo.addItem(f"{item['name']}（{item['price']:.2f} 元）", item["id"])

    def _create_treatment(self) -> None:
        item_id = self.treat_combo.currentData()
        if not item_id:
            self.treat_msg.setText("请先刷新并选择治疗项目")
            return
        try:
            order = self.api.create_treatment(
                self.treat_encounter_id.value(),
                item_id,
                self.treat_quantity.value(),
                self.treat_note.text().strip(),
            )
        except ApiError as e:
            self.treat_msg.setText(f"开单失败（{e.status_code}）：{e.detail}")
            return
        self.treat_msg.setText(f"治疗单已开立：{order['item_name']}（{order['id']}，待护士执行）")

