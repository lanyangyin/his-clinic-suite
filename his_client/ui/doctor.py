"""医生工作站：叫号接诊、结构化病历、开方（含用法）、检验检查开单、治疗开单。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
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
from his_client.labels import zh
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
        layout.addWidget(self.tabs)

    # ---------- 门诊工作台 ----------
    def _build_workbench_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        top.addWidget(QLabel("今日门诊队列（待接诊 + 今日已接诊）"))
        refresh = QPushButton("刷新队列")
        refresh.clicked.connect(self._load_workbench)
        top.addWidget(refresh)
        top.addStretch(1)
        layout.addLayout(top)

        self.wb_table = QTableWidget(0, 7)
        self.wb_table.setHorizontalHeaderLabels(
            ["挂号", "患者", "医生", "挂号状态", "就诊", "诊断", "待缴"]
        )
        self.wb_table.cellClicked.connect(self._select_workbench)
        layout.addWidget(self.wb_table, 1)

        self.wb_patient = QLabel("请选择患者")
        self.wb_patient.setStyleSheet("font-weight:bold;color:#0f172a")
        layout.addWidget(self.wb_patient)

        row = QHBoxLayout()
        self.wb_diagnosis = QLineEdit()
        self.wb_diagnosis.setPlaceholderText("诊断，如 急性上呼吸道感染")
        self.wb_start = QPushButton("开始接诊")
        self.wb_start.clicked.connect(self._start_workbench)
        row.addWidget(QLabel("诊断"))
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

    def _load_workbench(self) -> None:
        try:
            self.workbench_rows = self.api.doctor_worklist()
        except ApiError as e:
            self.wb_summary.setText(f"加载队列失败（{e.status_code}）：{e.detail}")
            return
        self.wb_table.setRowCount(len(self.workbench_rows))
        for row, item in enumerate(self.workbench_rows):
            gender = {"male": "男", "female": "女"}.get(item.get("gender"), "不详")
            age = item.get("age")
            allergy = item.get("allergy_label") or "不详"
            values = [
                str(item["registration_id"]),
                f"{item['patient_name']} · {gender}/{age if age is not None else '—'} · {allergy}",
                item["doctor_name"],
                zh("registration_status", item["registration_status"]),
                str(item.get("encounter_id") or "—"),
                item.get("diagnosis") or "—",
                f"{item.get('pending_amount', 0):.2f}",
            ]
            for col, value in enumerate(values):
                self.wb_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.wb_summary.setText(f"今日队列 {len(self.workbench_rows)} 人")

    def _select_workbench(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self.workbench_rows)):
            return
        item = self.workbench_rows[row]
        self.wb_current = item
        gender = {"male": "男", "female": "女"}.get(item.get("gender"), "不详")
        age = item.get("age")
        allergy = item.get("allergy_label") or "不详"
        self.wb_patient.setText(
            f"{item['patient_name']} · {gender}/{age if age is not None else '—'}岁 · "
            f"过敏：{allergy} · 挂号 {item['registration_id']} · "
            f"就诊 {item.get('encounter_id') or '未接诊'}"
        )
        self.wb_diagnosis.setText(item.get("diagnosis") or "")
        self.wb_start.setEnabled(not item.get("encounter_id"))
        if item.get("encounter_id"):
            self._load_workbench_summary(item["encounter_id"])
        else:
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
            f"诊断：{summary['diagnosis'] or '—'}　状态："
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
                item["registration_id"], self.wb_diagnosis.text().strip()
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

    def _switch_tab(self, text: str) -> None:
        for index in range(self.tabs.count()):
            if text in self.tabs.tabText(index):
                self.tabs.setCurrentIndex(index)
                return

    def _wb_record(self) -> None:
        self._switch_tab("病历")
        if hasattr(self, "mr_encounter_id") and self.wb_current:
            self._load_record()

    def _wb_prescribe(self) -> None:
        self._switch_tab("开方")

    def _wb_exam(self) -> None:
        self._switch_tab("检验")

    def _wb_treat(self) -> None:
        self._switch_tab("治疗")

    def _wb_history(self) -> None:
        self._switch_tab("历史诊疗")

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
        self.diagnosis = QLineEdit()
        self.diagnosis.setPlaceholderText("诊断，如：上呼吸道感染")
        start = QPushButton("开始接诊")
        start.clicked.connect(self._start_encounter)
        form.addRow("挂号 ID", self.reg_id)
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
                self.reg_id.value(), self.diagnosis.text().strip()
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
        self.mr_encounter_id.setRange(1, 10_000_000)
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
                encounter["diagnosis"],
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
        self.rx_encounter_id.setRange(1, 10_000_000)
        load = QPushButton("刷新药品目录")
        load.clicked.connect(self._load_drugs)
        top.addWidget(QLabel("就诊 ID"))
        top.addWidget(self.rx_encounter_id)
        top.addWidget(load)
        layout.addLayout(top)

        self.drug_table = QTableWidget(0, 6)
        self.drug_table.setHorizontalHeaderLabels(["ID", "药品", "规格", "单价", "医保比例", "医保类别"])
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
        self.rx_route = QLineEdit()
        self.rx_route.setPlaceholderText("如 口服 / 静滴")
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
        except ApiError as e:
            self.rx_msg.setText(f"加载药品失败：{e.detail}")
            return
        self.drug_table.setRowCount(len(drugs))
        for row, drug in enumerate(drugs):
            self.drug_table.setItem(row, 0, QTableWidgetItem(str(drug["id"])))
            self.drug_table.setItem(row, 1, QTableWidgetItem(drug["name"]))
            self.drug_table.setItem(row, 2, QTableWidgetItem(drug.get("spec") or ""))
            self.drug_table.setItem(row, 3, QTableWidgetItem(f"{drug['base_price']:.2f}"))
            self.drug_table.setItem(row, 4, QTableWidgetItem(str(drug["insurance_ratio"])))
            category = drug.get("insurance_category") or ""
            status = drug.get("insurance_match_status") or "unmatched"
            tag = f"{category}类" if category else ("歧义" if status == "ambiguous" else "未对码")
            self.drug_table.setItem(row, 5, QTableWidgetItem(tag))
        self.drug_table.cellClicked.connect(
            lambda row, _col: self.rx_drug_id.setText(self.drug_table.item(row, 0).text())
        )

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
            self.rx_msg.setText(f"开方失败（{e.status_code}）：{e.detail}")
            return
        warning = f"；医保提醒：{item['insurance_warning']}" if item.get("insurance_warning") else ""
        self.rx_msg.setText(f"开方成功：{item['drug_name']} × {item['quantity']}{warning}")
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
        self.exam_encounter_id.setRange(1, 10_000_000)
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
        self.treat_encounter_id.setRange(1, 10_000_000)
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

