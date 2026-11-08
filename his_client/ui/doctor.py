"""医生工作站：叫号接诊、结构化病历、开方（含用法）、检验检查开单、治疗开单。"""
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.labels import zh

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
        tabs = QTabWidget()
        tabs.addTab(self._build_register_tab(), "挂号")
        tabs.addTab(self._build_reception_tab(), "接诊")
        tabs.addTab(self._build_record_tab(), "病历")
        tabs.addTab(self._build_prescription_tab(), "开方")
        tabs.addTab(self._build_exam_tab(), "检验 / 检查")
        tabs.addTab(self._build_treatment_tab(), "治疗")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

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
                if e.status_code != 404:
                    raise
                record = self.api.create_medical_record(encounter_id, payload)
                action = "创建"
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

