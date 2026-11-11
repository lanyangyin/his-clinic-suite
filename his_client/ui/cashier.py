"""收费员工作站：患者建档/查询、挂号、收费/退费、打印。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme
from his_client.config import load_config
from his_client.labels import zh
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.patient_banner import PatientBanner
from his_client.ui.patient_info_panel import PatientInfoPanel
from his_client.ui.mixed_payment_dialog import MixedPaymentDialog


class CashierWidget(QWidget):
    def __init__(self, api: ApiClient, role: str = "cashier", parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.role = role
        self.insurance_enabled = load_config().insurance_enabled
        self.banner = PatientBanner()
        self.tabs = SidebarTabs()
        self.tabs.addTab(self._build_patient_tab(), "患者建档 / 查询")
        self.tabs.addTab(self._build_registration_tab(), "挂号")
        self.tabs.addTab(self._build_charge_tab(), "收费 / 退费")
        self.tabs.addTab(self._build_shift_tab(), "交班 / 日结")
        self.tabs.addTab(self._build_print_tab(), "打印")
        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        layout.addWidget(self.tabs)
        self._install_shortcuts()

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("F2"), self, activated=self._focus_patient_search)
        QShortcut(QKeySequence("F3"), self, activated=lambda: self.tabs.setCurrentIndex(2))
        QShortcut(QKeySequence("F8"), self, activated=lambda: self.tabs.setCurrentIndex(2))
        QShortcut(QKeySequence("Esc"), self, activated=self._clear_quick_filters)

    def _focus_patient_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.q_name.setFocus()
        self.q_name.selectAll()

    def _clear_quick_filters(self) -> None:
        if self.q_name.text() or self.q_id_number.text() or self.q_phone.text():
            self.q_name.clear()
            self.q_id_number.clear()
            self.q_phone.clear()
            self._query_patients()

    # ---------- 患者 ----------
    def _build_patient_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("新建 / 修改患者档案（P0 实名建档）")
        grid = QGridLayout(box)
        self.p_name = QLineEdit()
        self.p_gender = QComboBox()
        for value, label in (("unknown", "不详"), ("male", "男"), ("female", "女")):
            self.p_gender.addItem(label, value)
        self.p_id_type = QComboBox()
        for value, label in (
            ("id_card", "居民身份证"),
            ("passport", "护照"),
            ("hk_macau_taiwan", "港澳台证件"),
            ("other", "其他证件"),
            ("none", "无证件 / 无名氏"),
        ):
            self.p_id_type.addItem(label, value)
        self.p_id_number = QLineEdit()
        self.p_id_number.setPlaceholderText("身份证号 / 证件号；无证件可留空")
        self.p_birth_date = QLineEdit()
        self.p_birth_date.setPlaceholderText("YYYY-MM-DD，可留空由身份证带出")
        self.p_phone = QLineEdit()
        self.p_address = QLineEdit()
        self.p_address.setPlaceholderText("现住址，至少到区/街道")
        self.p_emergency_name = QLineEdit()
        self.p_emergency_relation = QLineEdit()
        self.p_emergency_phone = QLineEdit()
        self.p_insurance = QComboBox()
        for value, label in (
            ("employee", "职工医保"),
            ("resident", "居民医保"),
            ("remote", "异地医保"),
            ("self_pay", "自费"),
            ("commercial", "商业保险"),
            ("other", "其他"),
        ):
            self.p_insurance.addItem(label, value)
        self.p_allergy_status = QComboBox()
        for value, label in (
            ("unknown", "不详"),
            ("none", "无过敏史"),
            ("present", "有过敏史"),
        ):
            self.p_allergy_status.addItem(label, value)
        self.p_allergy_detail = QLineEdit()
        self.p_allergy_detail.setPlaceholderText("如 青霉素、头孢；无过敏可留空")
        self.p_privacy = QCheckBox("已向患者告知并取得信息采集授权")
        self.p_privacy.setChecked(True)

        row = 0
        grid.addWidget(QLabel("姓名*"), row, 0)
        grid.addWidget(self.p_name, row, 1)
        grid.addWidget(QLabel("性别*"), row, 2)
        grid.addWidget(self.p_gender, row, 3)
        row += 1
        grid.addWidget(QLabel("证件类型*"), row, 0)
        grid.addWidget(self.p_id_type, row, 1)
        grid.addWidget(QLabel("证件号码"), row, 2)
        grid.addWidget(self.p_id_number, row, 3)
        row += 1
        grid.addWidget(QLabel("出生日期*"), row, 0)
        grid.addWidget(self.p_birth_date, row, 1)
        grid.addWidget(QLabel("手机号*"), row, 2)
        grid.addWidget(self.p_phone, row, 3)
        row += 1
        grid.addWidget(QLabel("现住址*"), row, 0)
        grid.addWidget(self.p_address, row, 1, 1, 3)
        row += 1
        grid.addWidget(QLabel("紧急联系人*"), row, 0)
        grid.addWidget(self.p_emergency_name, row, 1)
        grid.addWidget(QLabel("关系"), row, 2)
        grid.addWidget(self.p_emergency_relation, row, 3)
        row += 1
        grid.addWidget(QLabel("联系人电话*"), row, 0)
        grid.addWidget(self.p_emergency_phone, row, 1)
        self.p_insurance_label = QLabel("医保类型*")
        grid.addWidget(self.p_insurance_label, row, 2)
        grid.addWidget(self.p_insurance, row, 3)
        if not self.insurance_enabled:
            self.p_insurance_label.setVisible(False)
            self.p_insurance.setVisible(False)
            self.p_insurance.setCurrentIndex(self.p_insurance.findData("self_pay"))
        row += 1
        grid.addWidget(QLabel("过敏史*"), row, 0)
        grid.addWidget(self.p_allergy_status, row, 1)
        grid.addWidget(self.p_allergy_detail, row, 2, 1, 2)
        row += 1
        grid.addWidget(self.p_privacy, row, 0, 1, 3)
        row += 1
        self.p_card_uid = QLineEdit()
        self.p_card_uid.setPlaceholderText("NFC 就诊卡号（刷卡或手输）")
        bind_card = QPushButton("绑定 NFC 卡")
        bind_card.clicked.connect(self._bind_patient_card)
        lookup_card = QPushButton("按卡查患者")
        lookup_card.clicked.connect(self._lookup_patient_card)
        grid.addWidget(QLabel("NFC 卡"), row, 0)
        grid.addWidget(self.p_card_uid, row, 1)
        card_buttons = QHBoxLayout()
        card_buttons.addWidget(bind_card)
        card_buttons.addWidget(lookup_card)
        grid.addLayout(card_buttons, row, 2, 1, 2)
        row += 1
        buttons = QHBoxLayout()
        create_btn = QPushButton("建档")
        create_btn.clicked.connect(self._create_patient)
        update_btn = QPushButton("更新选中档案")
        update_btn.clicked.connect(self._update_patient)
        clear_btn = QPushButton("清空表单")
        clear_btn.clicked.connect(self._clear_patient_form)
        buttons.addWidget(create_btn)
        buttons.addWidget(update_btn)
        buttons.addWidget(clear_btn)
        grid.addLayout(buttons, row, 3)
        layout.addWidget(box)

        query_box = QGroupBox("查询患者")
        query_layout = QHBoxLayout(query_box)
        self.q_name = QLineEdit()
        self.q_name.setPlaceholderText("姓名（可空）")
        self.q_id_number = QLineEdit()
        self.q_id_number.setPlaceholderText("身份证号/证件号（可空）")
        self.q_phone = QLineEdit()
        self.q_phone.setPlaceholderText("手机号（可空）")
        query_btn = QPushButton("查询")
        query_btn.clicked.connect(self._query_patients)
        query_layout.addWidget(self.q_name)
        query_layout.addWidget(self.q_id_number)
        query_layout.addWidget(self.q_phone)
        query_layout.addWidget(query_btn)
        layout.addWidget(query_box)

        self.patient_table = QTableWidget(0, 7)
        self.patient_table.setHorizontalHeaderLabels(
            ["ID", "患者编号", "姓名", "性别/年龄", "电话", "医保", "过敏"]
        )
        if not self.insurance_enabled:
            self.patient_table.setColumnHidden(5, True)
        self.patient_table.cellClicked.connect(self._select_patient_row)
        self.patient_table.cellDoubleClicked.connect(self._patient_to_registration)
        self.patient_table.setColumnHidden(0, True)
        layout.addWidget(self.patient_table)
        self.patient_rows: list[dict] = []

        self.patient_msg = QLabel("")
        self.patient_msg.setWordWrap(True)
        layout.addWidget(self.patient_msg)
        self.p_id_number.editingFinished.connect(self._derive_patient_fields)
        self.p_id_type.currentIndexChanged.connect(self._on_id_type_changed)
        return page

    def _on_id_type_changed(self) -> None:
        has_id = self.p_id_type.currentData() != "none"
        self.p_id_number.setEnabled(has_id)
        if not has_id:
            self.p_id_number.clear()

    def _derive_patient_fields(self) -> None:
        if self.p_id_type.currentData() != "id_card":
            return
        digits = self.p_id_number.text().strip()
        if len(digits) != 18 or not digits[:17].isdigit():
            return
        try:
            from datetime import date

            date(
                int(digits[6:10]), int(digits[10:12]), int(digits[12:14])
            )
        except ValueError:
            return
        if not self.p_birth_date.text().strip():
            self.p_birth_date.setText(f"{digits[6:10]}-{digits[10:12]}-{digits[12:14]}")
        if self.p_gender.currentData() == "unknown":
            self.p_gender.setCurrentIndex(
                self.p_gender.findData("male" if int(digits[16]) % 2 else "female")
            )

    def _patient_payload(self) -> dict:
        return {
            "name": self.p_name.text().strip(),
            "id_type": self.p_id_type.currentData(),
            "id_number": self.p_id_number.text().strip() or None,
            "gender": self.p_gender.currentData(),
            "birth_date": self.p_birth_date.text().strip() or None,
            "phone": self.p_phone.text().strip() or None,
            "address": self.p_address.text().strip(),
            "emergency_contact_name": self.p_emergency_name.text().strip(),
            "emergency_contact_relation": self.p_emergency_relation.text().strip(),
            "emergency_contact_phone": self.p_emergency_phone.text().strip(),
            "insurance_type": self.p_insurance.currentData(),
            "allergy_status": self.p_allergy_status.currentData(),
            "allergy_detail": self.p_allergy_detail.text().strip(),
            "privacy_consent": self.p_privacy.isChecked(),
        }

    def _validate_patient_payload(self, payload: dict) -> str:
        if not payload["name"]:
            return "请填写姓名"
        if payload["id_type"] != "none" and not payload["id_number"]:
            return "请填写证件号码，或选择无证件"
        if not payload["birth_date"]:
            return "请填写出生日期"
        if not payload["phone"]:
            return "请填写手机号"
        if not payload["address"]:
            return "请填写现住址"
        if not payload["emergency_contact_name"] or not payload["emergency_contact_phone"]:
            return "请填写紧急联系人和联系电话"
        if payload["gender"] == "unknown":
            return "请选择性别"
        if payload["allergy_status"] == "present" and not payload["allergy_detail"]:
            return "有过敏史时请填写过敏原"
        if not payload["privacy_consent"]:
            return "请先完成隐私告知并勾选授权"
        return ""

    def _confirm_duplicate(self, payload: dict) -> dict | None:
        try:
            check = self.api.check_patient_duplicates(
                name=payload["name"],
                id_number=payload["id_number"] or "",
                phone=payload["phone"] if payload["phone"] else "",
            )
        except ApiError as e:
            self.patient_msg.setText(f"查重失败（{e.status_code}）：{e.detail}")
            return None
        candidates = check.get("candidates") or []
        if not candidates:
            return None
        lines = [
            f"{row.get('patient_no') or row['id']} {row['name']} "
            f"{row.get('phone') or '无电话'}"
            for row in candidates[:5]
        ]
        text = "发现已有档案：\n" + "\n".join(lines) + "\n\n是否直接使用第一条档案？"
        answer = QMessageBox.question(
            self, "发现重复档案", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if answer == QMessageBox.Yes:
            return candidates[0]
        self.patient_msg.setText("已取消建档：请核对重复档案或修改证件信息")
        return None

    def _create_patient(self) -> None:
        payload = self._patient_payload()
        error = self._validate_patient_payload(payload)
        if error:
            self.patient_msg.setText(error)
            return
        duplicate = self._confirm_duplicate(payload)
        if duplicate is not None:
            self.patient_msg.setText(
                f"使用已有档案：{duplicate.get('patient_no') or duplicate['id']} "
                f"{duplicate['name']}"
            )
            self.q_name.setText(duplicate["name"])
            self._query_patients()
            return
        try:
            patient = self.api.create_patient(payload=payload)
        except ApiError as e:
            self.patient_msg.setText(f"建档失败（{e.status_code}）：{e.detail}")
            return
        self.patient_msg.setText(
            f"建档成功：{patient.get('patient_no') or patient['id']} "
            f"{patient['name']}，年龄 {patient.get('age') if patient.get('age') is not None else '—'}"
        )
        self._clear_patient_form(keep_message=True)
        self._query_patients()

    def _update_patient(self) -> None:
        row = self.patient_table.currentRow()
        if row < 0 or row >= len(self.patient_rows):
            self.patient_msg.setText("请先在下方列表选中要修改的档案")
            return
        payload = self._patient_payload()
        error = self._validate_patient_payload(payload)
        if error:
            self.patient_msg.setText(error)
            return
        try:
            patient = self.api.update_patient(self.patient_rows[row]["id"], payload)
        except ApiError as e:
            self.patient_msg.setText(f"更新失败（{e.status_code}）：{e.detail}")
            return
        self.patient_msg.setText(f"已更新档案：{patient.get('patient_no') or patient['id']}")
        self._query_patients()

    def _clear_patient_form(self, keep_message: bool = False) -> None:
        for field in (
            self.p_name, self.p_id_number, self.p_birth_date, self.p_phone,
            self.p_address, self.p_emergency_name, self.p_emergency_relation,
            self.p_emergency_phone, self.p_allergy_detail,
        ):
            field.clear()
        self.p_gender.setCurrentIndex(0)
        self.p_id_type.setCurrentIndex(0)
        self.p_insurance.setCurrentIndex(3)
        self.p_allergy_status.setCurrentIndex(0)
        self.p_privacy.setChecked(True)
        if not keep_message:
            self.patient_msg.clear()

    def _patient_to_registration(self, row: int, _col: int) -> None:
        self._select_patient_row(row, 0)
        if not (0 <= row < len(self.patient_rows)):
            return
        self.tabs.setCurrentIndex(1)
        self.r_patient_id.setValue(self.patient_rows[row]["id"])
        self._set_registration_patient_label(self.patient_rows[row])
        self.r_card_uid.clear()

    def _set_registration_patient_label(self, patient: dict) -> None:
        gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "不详")
        age = patient.get("age")
        allergy = patient.get("allergy_label") or "不详"
        self.r_patient_label.setText(
            f"患者：{patient.get('patient_no') or patient['id']} {patient['name']} · "
            f"{gender}/{age if age is not None else '—'}岁 · 过敏：{allergy}"
        )
        self.r_patient_label.setStyleSheet(
            "font-weight:bold;color:#f87171"
            if allergy not in ("无过敏史", "不详", "过敏史不详")
            else "font-weight:bold;color:#e2e8f0"
        )

    def _bind_patient_card(self) -> None:
        row = self.patient_table.currentRow()
        if row < 0 or row >= len(self.patient_rows):
            self.patient_msg.setText("请先在患者列表选中要绑卡的人")
            return
        card_uid = self.p_card_uid.text().strip()
        if not card_uid:
            self.patient_msg.setText("请刷卡或输入 NFC 卡号")
            return
        try:
            card = self.api.issue_patient_card(self.patient_rows[row]["id"], card_uid)
        except ApiError as e:
            self.patient_msg.setText(f"绑卡失败（{e.status_code}）：{e.detail}")
            return
        self.patient_msg.setText(
            f"已绑定 NFC 卡：{card['card_uid']} → {card['patient_no'] or card['patient_id']} "
            f"{card['patient_name']}"
        )

    def _lookup_patient_card(self) -> None:
        card_uid = self.p_card_uid.text().strip()
        if not card_uid:
            self.patient_msg.setText("请刷卡或输入 NFC 卡号")
            return
        try:
            found = self.api.get_patient_by_card(card_uid)
        except ApiError as e:
            self.patient_msg.setText(f"读卡失败（{e.status_code}）：{e.detail}")
            return
        patient = found["patient"]
        self.banner.set_patient(patient)
        self.q_name.setText(patient["name"])
        self.q_phone.setText(patient.get("phone") or "")
        self._query_patients()
        self.patient_msg.setText(
            f"NFC 卡 {card_uid} → {patient.get('patient_no') or patient['id']} "
            f"{patient['name']}，可直接挂号"
        )

    def _select_patient_row(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self.patient_rows)):
            return
        patient = self.patient_rows[row]
        self.banner.set_patient(patient)
        self.p_name.setText(patient.get("name") or "")
        index = self.p_gender.findData(patient.get("gender") or "unknown")
        self.p_gender.setCurrentIndex(max(0, index))
        index = self.p_id_type.findData(patient.get("id_type") or "id_card")
        self.p_id_type.setCurrentIndex(max(0, index))
        self.p_id_number.setText(patient.get("id_number") or "")
        self.p_birth_date.setText(patient.get("birth_date") or "")
        self.p_phone.setText(patient.get("phone") or "")
        self.p_address.setText(patient.get("address") or "")
        self.p_emergency_name.setText(patient.get("emergency_contact_name") or "")
        self.p_emergency_relation.setText(patient.get("emergency_contact_relation") or "")
        self.p_emergency_phone.setText(patient.get("emergency_contact_phone") or "")
        index = self.p_insurance.findData(patient.get("insurance_type") or "self_pay")
        self.p_insurance.setCurrentIndex(max(0, index))
        index = self.p_allergy_status.findData(patient.get("allergy_status") or "unknown")
        self.p_allergy_status.setCurrentIndex(max(0, index))
        self.p_allergy_detail.setText(patient.get("allergy_detail") or "")
        self.p_privacy.setChecked(bool(patient.get("privacy_consent_at")))
        self.patient_msg.setText(
            f"当前档案：{patient.get('patient_no') or patient['id']} {patient['name']}"
        )

    def _query_patients(self) -> None:
        try:
            rows = self.api.list_patients(
                name=self.q_name.text().strip() or None,
                id_number=self.q_id_number.text().strip() or None,
                phone=self.q_phone.text().strip() or None,
            )
        except ApiError as e:
            self.patient_msg.setText(f"查询失败：{e.detail}")
            return
        self.patient_rows = rows
        self.patient_table.setRowCount(len(rows))
        for row, patient in enumerate(rows):
            age = patient.get("age")
            gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "不详")
            insurance = {
                "employee": "职工", "resident": "居民", "remote": "异地",
                "self_pay": "自费", "commercial": "商保", "other": "其他",
            }.get(patient.get("insurance_type"), patient.get("insurance_type") or "")
            values = [
                str(patient["id"]),
                patient.get("patient_no") or "—",
                patient["name"],
                f"{gender}/{age if age is not None else '—'}",
                patient.get("phone") or "—",
                insurance,
                patient.get("allergy_label") or "不详",
            ]
            for col, value in enumerate(values):
                self.patient_table.setItem(row, col, QTableWidgetItem(str(value)))

    # ---------- 挂号 ----------
    def _build_registration_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        quick = QGroupBox("快速挂号（姓名/性别/电话先挂号，证件地址后补）")
        quick_row = QHBoxLayout(quick)
        self.qr_name = QLineEdit()
        self.qr_name.setPlaceholderText("姓名*")
        self.qr_gender = QComboBox()
        self.qr_gender.addItem("男", "male")
        self.qr_gender.addItem("女", "female")
        self.qr_phone = QLineEdit()
        self.qr_phone.setPlaceholderText("手机号*")
        self.qr_id_number = QLineEdit()
        self.qr_id_number.setPlaceholderText("身份证号（可空，后补）")
        quick_btn = QPushButton("快速建档并挂号")
        quick_btn.clicked.connect(self._quick_register)
        quick_row.addWidget(self.qr_name)
        quick_row.addWidget(self.qr_gender)
        quick_row.addWidget(self.qr_phone)
        quick_row.addWidget(self.qr_id_number)
        quick_row.addWidget(quick_btn)
        layout.addWidget(quick)

        box = QGroupBox("现场挂号")
        form = QFormLayout(box)
        self.r_patient_id = QSpinBox()
        self.r_patient_id.setRange(0, 10_000_000)
        self.r_patient_id.setSpecialValueText("扫码/选择患者")
        self.r_patient_id.setReadOnly(True)
        self.r_patient_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.r_schedule_id = QSpinBox()
        self.r_schedule_id.setRange(0, 10_000_000)
        self.r_schedule_id.setSpecialValueText("不选排班")
        self.r_doctor_combo = QLineEdit()
        self.r_doctor_combo.setPlaceholderText("医生 ID")
        self.r_doctor_combo.setReadOnly(True)
        self.r_doctor_list = QTableWidget(0, 2)
        self.r_doctor_list.setHorizontalHeaderLabels(["", "医生 / 科室"])
        self.r_doctor_list.setColumnHidden(0, True)
        self.r_doctor_list.setMaximumHeight(160)
        self.r_doctor_list.cellClicked.connect(self._pick_doctor)
        self.r_doctor_search = QLineEdit()
        self.r_doctor_search.setPlaceholderText("搜索医生姓名/科室")
        self.r_doctor_search.setClearButtonEnabled(True)
        self.r_doctor_search.textChanged.connect(self._filter_doctors)
        self.r_doctor_label = QLabel("已选医生：—")
        self.r_doctor_label.setStyleSheet("font-weight:bold;color:#e2e8f0")
        refresh_btn = QPushButton("刷新医生列表")
        refresh_btn.clicked.connect(self._load_doctors)
        doctor_box = QWidget()
        doctor_layout = QVBoxLayout(doctor_box)
        doctor_layout.setContentsMargins(0, 0, 0, 0)
        doctor_layout.addWidget(self.r_doctor_search)
        doctor_layout.addWidget(self.r_doctor_list)
        row = QHBoxLayout()
        row.addWidget(doctor_box)
        form.addRow("患者", self.r_patient_id)
        self.r_patient_label = QLabel("患者：—")
        self.r_patient_label.setStyleSheet("font-weight:bold;color:#e2e8f0")
        form.addRow("", self.r_patient_label)
        self.r_card_uid = QLineEdit()
        self.r_card_uid.setPlaceholderText("NFC 就诊卡号")
        lookup_card = QPushButton("按卡带出患者")
        lookup_card.clicked.connect(self._lookup_registration_card)
        card_row = QHBoxLayout()
        card_row.addWidget(self.r_card_uid)
        card_row.addWidget(lookup_card)
        form.addRow("NFC 卡", card_row)
        form.addRow("医生", row)
        form.addRow("", self.r_doctor_label)
        form.addRow("", refresh_btn)
        form.addRow("排班 ID（可选）", self.r_schedule_id)
        submit = QPushButton("挂号")
        submit.clicked.connect(self._create_registration)
        form.addRow("", submit)
        layout.addWidget(box)

        self.reg_msg = QLabel("")
        self.reg_msg.setWordWrap(True)
        layout.addWidget(self.reg_msg)
        layout.addStretch(1)
        return page

    def _load_doctors(self) -> None:
        try:
            self.r_doctor_rows = self.api.list_doctors()
        except ApiError as e:
            self.reg_msg.setText(f"加载医生失败：{e.detail}")
            return
        self._filter_doctors()

    def _filter_doctors(self) -> None:
        term = self.r_doctor_search.text().strip().lower()
        rows = getattr(self, "r_doctor_rows", [])
        if term:
            rows = [
                doctor
                for doctor in rows
                if term in str(doctor.get("name", "")).lower()
                or term in str(doctor.get("department_id", "")).lower()
            ]
        self.r_doctor_list.setRowCount(len(rows))
        for row, doctor in enumerate(rows):
            self.r_doctor_list.setItem(row, 0, QTableWidgetItem(str(doctor["id"])))
            self.r_doctor_list.setItem(
                row, 1, QTableWidgetItem(f'{doctor["name"]}（科室 {doctor["department_id"]}）')
            )

    def _pick_doctor(self, row: int, _column: int) -> None:
        item = self.r_doctor_list.item(row, 0)
        if item:
            self.r_doctor_combo.setText(item.text())
            name_cell = self.r_doctor_list.item(row, 1)
            self.r_doctor_label.setText(
                f"已选医生：{name_cell.text() if name_cell else item.text()}"
            )

    def _lookup_registration_card(self) -> None:
        card_uid = self.r_card_uid.text().strip()
        if not card_uid:
            self.reg_msg.setText("请刷卡或输入 NFC 卡号")
            return
        try:
            found = self.api.get_patient_by_card(card_uid)
        except ApiError as e:
            self.reg_msg.setText(f"读卡失败（{e.status_code}）：{e.detail}")
            return
        patient = found["patient"]
        self.banner.set_patient(patient)
        self.r_patient_id.setValue(patient["id"])
        self._set_registration_patient_label(patient)
        self.reg_msg.setText(
            f"已带出患者：{patient.get('patient_no') or patient['id']} {patient['name']}"
        )

    def _quick_register(self) -> None:
        name = self.qr_name.text().strip()
        phone = self.qr_phone.text().strip()
        if not name or not phone:
            self.reg_msg.setText("快速挂号至少填写姓名和手机号")
            return
        try:
            doctor_id = int(self.r_doctor_combo.text())
        except ValueError:
            self.reg_msg.setText("请先在下方刷新医生列表并选择医生")
            return
        payload = {
            "name": name,
            "gender": self.qr_gender.currentData(),
            "phone": phone,
            "id_type": "id_card" if self.qr_id_number.text().strip() else "none",
            "id_number": self.qr_id_number.text().strip() or None,
            "address": "待补录",
            "emergency_contact_name": "",
            "emergency_contact_relation": "",
            "emergency_contact_phone": "",
            "insurance_type": "self_pay",
            "allergy_status": "unknown",
            "allergy_detail": "",
            "privacy_consent": True,
        }
        try:
            patient = self.api.create_patient(payload=payload)
            registration = self.api.create_registration(
                patient["id"], doctor_id, self.r_schedule_id.value() or None
            )
        except ApiError as e:
            self.reg_msg.setText(f"快速挂号失败（{e.status_code}）：{e.detail}")
            return
        self.r_patient_id.setValue(patient["id"])
        self.banner.set_patient(patient)
        self._set_registration_patient_label(patient)
        self.reg_msg.setText(
            f"快速挂号成功：{patient['name']}，挂号 ID {registration['id']}；"
            "证件/地址/紧急联系人请后补"
        )
        self.qr_name.clear()
        self.qr_phone.clear()
        self.qr_id_number.clear()

    def _create_registration(self) -> None:
        try:
            doctor_id = int(self.r_doctor_combo.text())
        except ValueError:
            self.reg_msg.setText("请先刷新医生列表并选择医生")
            return
        schedule_id = self.r_schedule_id.value() or None
        try:
            registration = self.api.create_registration(
                self.r_patient_id.value(), doctor_id, schedule_id
            )
        except ApiError as e:
            self.reg_msg.setText(f"挂号失败（{e.status_code}）：{e.detail}")
            return
        self.reg_msg.setText(
            f"挂号成功：挂号 ID {registration['id']}，状态 {zh('registration_status', registration['status'])}"
        )

    # ---------- 收费 / 退费 ----------
    def _build_charge_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("就诊费用")
        box_layout = QVBoxLayout(box)
        scan_row = QHBoxLayout()
        self.c_scan_code = QLineEdit()
        self.c_scan_code.setPlaceholderText("扫处方条码（RX.../中药处方码），回车带出")
        self.c_scan_code.returnPressed.connect(self._scan_barcode)
        scan_btn = QPushButton("扫码带出")
        scan_btn.clicked.connect(self._scan_barcode)
        scan_row.addWidget(self.c_scan_code)
        scan_row.addWidget(scan_btn)
        self.c_scan_status = QLabel("")
        self.c_scan_status.setWordWrap(True)
        scan_row.addWidget(self.c_scan_status)
        box_layout.addLayout(scan_row)

        row = QHBoxLayout()
        self.c_encounter_id = QSpinBox()
        self.c_encounter_id.setRange(0, 10_000_000)
        self.c_encounter_id.setSpecialValueText("扫码带出")
        self.c_encounter_id.setReadOnly(True)
        self.c_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        query_btn = QPushButton("查询费用")
        query_btn.clicked.connect(self._load_charges)
        pay_btn = QPushButton("收费")
        pay_btn.clicked.connect(self._pay)
        mixed_btn = QPushButton("混合支付 / 折扣")
        mixed_btn.clicked.connect(self._mixed_pay)
        row.addWidget(QLabel("就诊"))
        row.addWidget(self.c_encounter_id)
        row.addWidget(query_btn)
        row.addWidget(pay_btn)
        row.addWidget(mixed_btn)
        self.c_patient_label = QLabel("当前患者：—")
        self.c_patient_label.setStyleSheet("font-weight:bold;color:#e2e8f0")
        box_layout.addLayout(row)
        box_layout.addWidget(self.c_patient_label)

        method_row = QHBoxLayout()
        self.c_channel = QComboBox()
        channels = [
            ("现金", "cash"),
            ("微信支付", "wechat"),
            ("支付宝", "alipay"),
            ("POS 刷卡", "pos"),
        ]
        if self.insurance_enabled:
            channels.append(("医保卡", "insurance_card"))
        for label, value in channels:
            self.c_channel.addItem(label, value)
        self.c_auth_code = QLineEdit()
        self.c_auth_code.setPlaceholderText("付款码（微信/支付宝）")
        self.c_card_no = QLineEdit()
        self.c_card_no.setPlaceholderText("卡号/读卡返回值（POS）")
        method_row.addWidget(QLabel("支付方式"))
        method_row.addWidget(self.c_channel)
        method_row.addWidget(self.c_auth_code)
        method_row.addWidget(self.c_card_no)
        box_layout.addLayout(method_row)
        self.c_channel.currentIndexChanged.connect(self._update_payment_inputs)
        self._update_payment_inputs()

        self.charge_table = QTableWidget(0, 5)
        self.charge_table.setHorizontalHeaderLabels(["类型", "项目", "数量", "金额", "状态"])
        box_layout.addWidget(self.charge_table)
        self.charge_msg = QLabel("")
        self.charge_msg.setWordWrap(True)
        box_layout.addWidget(self.charge_msg)
        self.charge_info = PatientInfoPanel()
        body = QHBoxLayout()
        body.addWidget(self.charge_info)
        body.addWidget(box, 1)
        layout.addLayout(body)

        refund_box = QGroupBox("按明细退费（可只退一种药/一颗药）")
        refund_layout = QVBoxLayout(refund_box)
        refund_top = QHBoxLayout()
        self.refund_payment_id = QSpinBox()
        self.refund_payment_id.setRange(1, 10_000_000)
        load_refund = QPushButton("加载收费明细")
        load_refund.clicked.connect(self._load_refund_charges)
        refund_all = QPushButton("全部退")
        refund_all.clicked.connect(self._refund_all)
        refund_top.addWidget(QLabel("收费单"))
        refund_top.addWidget(self.refund_payment_id)
        refund_top.addWidget(load_refund)
        refund_top.addWidget(refund_all)
        refund_layout.addLayout(refund_top)
        self.refund_patient_label = QLabel("当前患者：—")
        self.refund_patient_label.setStyleSheet("font-weight:bold;color:#e2e8f0")
        refund_layout.addWidget(self.refund_patient_label)

        refund_row = QHBoxLayout()
        self.refund_qty = QSpinBox()
        self.refund_qty.setRange(1, 10000)
        self.refund_selected_btn = QPushButton("退所选数量")
        self.refund_selected_btn.clicked.connect(self._refund_selected)
        refund_row.addWidget(QLabel("本次退数量"))
        refund_row.addWidget(self.refund_qty)
        refund_row.addWidget(self.refund_selected_btn)
        refund_row.addStretch(1)
        refund_layout.addLayout(refund_row)

        self.refund_rule = QLabel("")
        self.refund_rule.setWordWrap(True)
        refund_layout.addWidget(self.refund_rule)

        self.refund_table = QTableWidget(0, 7)
        self.refund_table.setHorizontalHeaderLabels(
            ["明细 ID", "类型", "项目", "数量", "已退", "可退", "单价"]
        )
        self.refund_table.setColumnHidden(0, True)
        self.refund_table.cellClicked.connect(self._select_refund_charge)
        refund_layout.addWidget(self.refund_table)
        self.refund_charge_id: int | None = None
        layout.addWidget(refund_box)

        self.refund_msg = QLabel("")
        self.refund_msg.setWordWrap(True)
        layout.addWidget(self.refund_msg)
        layout.addStretch(1)
        return page

    def _update_payment_inputs(self) -> None:
        channel = self.c_channel.currentData() if hasattr(self, "c_channel") else "cash"
        self.c_auth_code.setEnabled(channel in ("wechat", "alipay"))
        self.c_card_no.setEnabled(channel in ("pos", "insurance_card"))

    def _scan_barcode(self) -> None:
        code = self.c_scan_code.text().strip()
        if not code:
            self.charge_msg.setText("请扫描处方条码")
            return
        try:
            row = self.api.resolve_prescription_barcode(code)
        except ApiError as e:
            self.charge_msg.setText(f"条码解析失败（{e.status_code}）：{e.detail}")
            return
        self.c_encounter_id.setValue(row["encounter_id"])
        self.banner.set_patient(
            {"id": row.get("patient_id"), "name": row.get("patient_name")},
            row["encounter_id"],
            row.get("status_text") or "",
        )
        self._load_charges()
        if row["is_paid"]:
            self.c_scan_status.setStyleSheet("color:#f87171;font-weight:bold")
            self.c_scan_status.setText(
                f"已收费：{row['patient_name']}，不能重复收费"
            )
        else:
            self.c_scan_status.setStyleSheet("color:#86efac;font-weight:bold")
            self.c_scan_status.setText(
                f"未收费：{row['patient_name']}，待收 {row['pending_amount']:.2f} 元"
            )

    def _show_encounter_patient(self, encounter_id: int, label: QLabel) -> None:
        if hasattr(self, "charge_info") and label is self.c_patient_label:
            self.charge_info.clear()
        try:
            encounter = self.api.get_encounter(encounter_id)
            registration = self.api.get_registration(encounter["registration_id"])
            patient = self.api.get_patient(registration["patient_id"])
        except (ApiError, KeyError) as e:
            detail = e.detail if isinstance(e, ApiError) else str(e)
            label.setText(f"当前患者：读取失败（{detail}）")
            return
        gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "不详")
        age = patient.get("age")
        allergy = patient.get("allergy_label") or "不详"
        label.setText(
            f"当前患者：{patient.get('patient_no') or patient['id']} "
            f"{patient['name']} · {gender}/{age if age is not None else '—'}岁 · "
            f"过敏：{allergy} · 电话：{patient.get('phone') or '—'}"
        )
        if hasattr(self, "charge_info") and label is self.c_patient_label:
            self.charge_info.set_patient(
                patient,
                encounter_id,
                "收费窗口",
            )
        label.setStyleSheet(
            "font-weight:bold;color:#f87171"
            if allergy not in ("无过敏史", "不详", "过敏史不详")
            else "font-weight:bold;color:#e2e8f0"
        )

    def _mixed_pay(self) -> None:
        encounter_id = self.c_encounter_id.value()
        if not encounter_id:
            self.charge_msg.setText("请先扫码带出就诊")
            return
        try:
            summary = self.api.get_charge_summary(encounter_id)
        except ApiError as e:
            self.charge_msg.setText(f"查询失败（{e.status_code}）：{e.detail}")
            return
        total = round(summary.get("total_pending", 0), 2)
        if total <= 0:
            self.charge_msg.setText("没有待收费用")
            return
        dialog = MixedPaymentDialog(total, self.role in ("admin", "director"), self)
        if dialog.exec() != dialog.Accepted:
            return
        payload = dialog.payload()
        allocations = payload["allocations"]
        discount = payload["discount_amount"]
        try:
            if len(allocations) == 1 and not discount:
                payment = self.api.create_payment(
                    encounter_id, channel=allocations[0]["channel"]
                )
            else:
                payment = self.api.create_payment(
                    encounter_id,
                    allocations=allocations,
                    discount_amount=discount,
                    discount_reason=payload["discount_reason"],
                )
        except ApiError as e:
            self.charge_msg.setText(f"收费失败（{e.status_code}）：{e.detail}")
            return
        self.charge_msg.setText(
            f"收费成功：单号 {payment['id']}，应收 {payment['amount']:.2f}，"
            f"优惠 {payment.get('discount_amount', 0):.2f}，"
            f"实收自费 {payment['self_pay_amount']:.2f}"
        )
        self.refund_payment_id.setValue(payment["id"])
        self._load_charges()

    def _load_charges(self) -> None:
        encounter_id = self.c_encounter_id.value()
        self._show_encounter_patient(encounter_id, self.c_patient_label)
        try:
            charges = self.api.get_charges(encounter_id)
            summary = self.api.get_charge_summary(encounter_id)
        except ApiError as e:
            self.charge_msg.setText(f"查询失败（{e.status_code}）：{e.detail}")
            return
        self.charge_table.setRowCount(len(charges))
        for row, charge in enumerate(charges):
            self.charge_table.setItem(row, 0, QTableWidgetItem(zh('charge_type', charge["charge_type"])))
            self.charge_table.setItem(row, 1, QTableWidgetItem(charge["item_name"]))
            self.charge_table.setItem(row, 2, QTableWidgetItem(str(charge["quantity"])))
            self.charge_table.setItem(row, 3, QTableWidgetItem(f"{charge['amount']:.2f}"))
            self.charge_table.setItem(row, 4, QTableWidgetItem(zh('charge_status', charge["status"])))
        self.charge_msg.setText(
            f"待收 {summary['total_pending']:.2f} 元；已收 {summary['total_paid']:.2f} 元"
            + ("；当前按全自费" if not self.insurance_enabled else "")
        )

    def _pay(self) -> None:
        channel = self.c_channel.currentData()
        try:
            payment = self.api.create_payment(
                self.c_encounter_id.value(),
                channel=channel,
                auth_code=self.c_auth_code.text().strip(),
                card_no=self.c_card_no.text().strip(),
            )
        except ApiError as e:
            self.charge_msg.setText(f"收费失败（{e.status_code}）：{e.detail}")
            return
        self.charge_msg.setText(
            f"收费成功：单号 {payment['id']}，金额 {payment['amount']:.2f} 元，"
            + (
                f"医保 {payment['insurance_amount']:.2f}，自费 {payment['self_pay_amount']:.2f}，"
                if self.insurance_enabled
                else "实收 "
            )
            + f"方式 {zh('payment_channel', payment.get('channel'))}"
            + (f"，交易号 {payment['channel_trade_no']}" if payment.get("channel_trade_no") else "")
        )
        self.refund_payment_id.setValue(payment["id"])
        self._load_charges()

    def _load_refund_charges(self) -> None:
        payment_id = self.refund_payment_id.value()
        try:
            payment = self.api.get_payment(payment_id)
            charges = self.api.get_charges(payment["encounter_id"])
        except ApiError as e:
            self.refund_msg.setText(f"加载收费明细失败（{e.status_code}）：{e.detail}")
            return
        self._show_encounter_patient(
            payment["encounter_id"], self.refund_patient_label
        )
        self.refund_table.setRowCount(len(charges))
        for row, charge in enumerate(charges):
            refunded = charge.get("refunded_quantity", 0)
            values = [
                str(charge["id"]),
                zh("charge_type", charge["charge_type"]),
                charge["item_name"],
                str(charge["quantity"]),
                str(refunded),
                str(charge["quantity"] - refunded),
                f"{charge['unit_price']:.2f}",
            ]
            for col, value in enumerate(values):
                self.refund_table.setItem(row, col, QTableWidgetItem(value))
        self.refund_charge_id = None
        insurance = payment.get("insurance_amount", 0) or 0
        insurance_only = insurance > 0 or payment.get("channel") == "insurance_card"
        if insurance_only:
            self.refund_selected_btn.setEnabled(False)
            self.refund_rule.setText(
                "该收费需整单全额退（点「全部退」），不能按明细/数量部分退。"
            )
        else:
            self.refund_selected_btn.setEnabled(True)
            self.refund_rule.setText("全自费收费：可选择明细并填写数量，只退其中一种药或一颗药。")
        self.refund_msg.setText(
            f"收费单 {payment['id']}，状态 {zh('payment_status', payment['status'])}，"
            f"已退 {payment.get('refunded_amount', 0):.2f} 元"
        )

    def _select_refund_charge(self, row: int, _col: int) -> None:
        item = self.refund_table.item(row, 0)
        remaining = self.refund_table.item(row, 5)
        if not item or not remaining:
            return
        self.refund_charge_id = int(item.text())
        left = int(remaining.text())
        self.refund_qty.setMaximum(max(left, 1))
        self.refund_qty.setValue(1 if left > 0 else 1)

    def _refund_selected(self) -> None:
        if not self.refund_selected_btn.isEnabled():
            self.refund_msg.setText("该收费需整单全额退")
            return
        if not self.refund_charge_id:
            self.refund_msg.setText("请先在明细中选择要退的项目")
            return
        try:
            payment = self.api.refund_payment(
                self.refund_payment_id.value(),
                items=[
                    {
                        "charge_id": self.refund_charge_id,
                        "quantity": self.refund_qty.value(),
                    }
                ],
            )
        except ApiError as e:
            self.refund_msg.setText(f"退费失败（{e.status_code}）：{e.detail}")
            return
        self.refund_msg.setText(
            f"退费成功：单号 {payment['id']}，状态 {zh('payment_status', payment['status'])}，"
            f"累计已退 {payment.get('refunded_amount', 0):.2f} 元"
        )
        self.refund_charge_id = None
        self._load_refund_charges()

    def _refund_all(self) -> None:
        try:
            payment = self.api.refund_payment(self.refund_payment_id.value())
        except ApiError as e:
            self.refund_msg.setText(f"退费失败（{e.status_code}）：{e.detail}")
            return
        self.refund_msg.setText(
            f"全部退费成功：单号 {payment['id']}，状态 {zh('payment_status', payment['status'])}"
        )
        self._load_refund_charges()

    # ---------- 打印 ----------
    def _build_print_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box1 = QGroupBox("打印处方")
        row1 = QHBoxLayout(box1)
        self.pr_encounter_id = QSpinBox()
        self.pr_encounter_id.setRange(1, 10_000_000)
        open_pr = QPushButton("打开处方打印页")
        open_pr.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(self.api.prescription_print_url(self.pr_encounter_id.value()))
            )
        )
        row1.addWidget(QLabel("就诊 ID"))
        row1.addWidget(self.pr_encounter_id)
        row1.addWidget(open_pr)
        layout.addWidget(box1)

        box2 = QGroupBox("打印收费小票")
        row2 = QHBoxLayout(box2)
        self.pr_payment_id = QSpinBox()
        self.pr_payment_id.setRange(1, 10_000_000)
        open_rc = QPushButton("打开小票打印页")
        open_rc.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(self.api.receipt_print_url(self.pr_payment_id.value()))
            )
        )
        row2.addWidget(QLabel("收费单 ID"))
        row2.addWidget(self.pr_payment_id)
        row2.addWidget(open_rc)
        layout.addWidget(box2)

        box3 = QGroupBox("发票打印 / 作废")
        row3 = QHBoxLayout(box3)
        print_btn = QPushButton("登记打印")
        print_btn.clicked.connect(self._print_invoice)
        self.void_reason = QLineEdit()
        self.void_reason.setPlaceholderText("作废原因")
        void_btn = QPushButton("作废发票")
        void_btn.clicked.connect(self._void_invoice)
        row3.addWidget(print_btn)
        row3.addWidget(self.void_reason)
        row3.addWidget(void_btn)
        layout.addWidget(box3)
        self.invoice_msg = QLabel("")
        layout.addWidget(self.invoice_msg)

        layout.addStretch(1)
        return page


    # ---------- 交班 / 日结 ----------
    def _build_shift_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        open_box = QGroupBox("开班")
        form = QFormLayout(open_box)
        self.opening_float = QDoubleSpinBox()
        self.opening_float.setRange(0, 1000000)
        self.opening_float.setDecimals(2)
        self.shift_note = QLineEdit()
        open_btn = QPushButton("开班")
        open_btn.clicked.connect(self._open_shift)
        form.addRow("备用金", self.opening_float)
        form.addRow("备注", self.shift_note)
        form.addRow("", open_btn)
        layout.addWidget(open_box)

        close_box = QGroupBox("交班")
        close_form = QFormLayout(close_box)
        self.counted_cash = QDoubleSpinBox()
        self.counted_cash.setRange(0, 10000000)
        self.counted_cash.setDecimals(2)
        close_btn = QPushButton("交班")
        close_btn.clicked.connect(self._close_shift)
        close_form.addRow("实收现金", self.counted_cash)
        close_form.addRow("", close_btn)
        layout.addWidget(close_box)

        top = QHBoxLayout()
        refresh = QPushButton("刷新日结")
        refresh.clicked.connect(self._load_daily)
        top.addWidget(refresh)
        top.addStretch(1)
        layout.addLayout(top)
        self.shift_summary = QLabel("")
        self.shift_summary.setWordWrap(True)
        layout.addWidget(self.shift_summary)
        self.channel_table = QTableWidget(0, 4)
        self.channel_table.setHorizontalHeaderLabels(["渠道", "笔数", "金额", "已退"])
        layout.addWidget(self.channel_table)
        self.shift_table = QTableWidget(0, 6)
        self.shift_table.setHorizontalHeaderLabels(
            ["交班单", "收费员", "备用金", "应有现金", "实收", "差异"]
        )
        layout.addWidget(self.shift_table)
        self.shift_msg = QLabel("")
        layout.addWidget(self.shift_msg)
        self._load_daily()
        return page

    def _load_daily(self) -> None:
        try:
            data = self.api.cashier_daily()
        except ApiError as e:
            self.shift_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.shift_data = data
        self.shift_summary.setText(
            f"{data['date']}　收费 {data['payment_count']} 笔　"
            f"总额 {data['amount']:.2f}　净收入 {data['net']:.2f}　待收费 {data['pending_amount']:.2f}"
        )
        self.channel_table.setRowCount(len(data["channels"]))
        for row, item in enumerate(data["channels"]):
            values = [item["label"], item["count"], f"{item['amount']:.2f}", f"{item['refunded']:.2f}"]
            for col, value in enumerate(values):
                self.channel_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.shift_table.setRowCount(len(data["shifts"]))
        self.open_shift_id = None
        for row, item in enumerate(data["shifts"]):
            values = [
                item["shift_no"],
                item["cashier"],
                f"{item['opening_float']:.2f}",
                f"{item['expected_cash']:.2f}" if item["expected_cash"] is not None else "—",
                f"{item['counted_cash']:.2f}" if item["counted_cash"] is not None else "—",
                f"{item['difference']:.2f}" if item["difference"] is not None else "—",
            ]
            for col, value in enumerate(values):
                self.shift_table.setItem(row, col, QTableWidgetItem(str(value)))
            if item["status"] == "open":
                self.open_shift_id = item["id"]
        self.shift_msg.setText(f"日结已刷新；{'当前有未交班记录' if self.open_shift_id else '当前无未交班记录'}")

    def _open_shift(self) -> None:
        try:
            shift = self.api.open_cashier_shift(
                self.opening_float.value(), self.shift_note.text().strip()
            )
        except ApiError as e:
            self.shift_msg.setText(f"开班失败（{e.status_code}）：{e.detail}")
            return
        self.shift_msg.setText(f"已开班：{shift['shift_no']}")
        self._load_daily()

    def _close_shift(self) -> None:
        shift_id = getattr(self, "open_shift_id", None)
        if not shift_id:
            self.shift_msg.setText("没有待交班记录")
            return
        try:
            shift = self.api.close_cashier_shift(
                shift_id, self.counted_cash.value(), self.shift_note.text().strip()
            )
        except ApiError as e:
            self.shift_msg.setText(f"交班失败（{e.status_code}）：{e.detail}")
            return
        self.shift_msg.setText(
            f"已交班，应有 {shift['expected_cash']:.2f}，差异 {shift['difference']:.2f}"
        )
        self._load_daily()

    def _print_invoice(self) -> None:
        try:
            row = self.api.print_invoice(self.pr_payment_id.value())
        except ApiError as e:
            self.invoice_msg.setText(f"打印登记失败（{e.status_code}）：{e.detail}")
            return
        self.invoice_msg.setText(
            f"发票 {row['invoice_no']} 已登记打印，第 {row['print_count']} 次"
        )
        QDesktopServices.openUrl(
            QUrl(self.api.receipt_print_url(self.pr_payment_id.value()))
        )

    def _void_invoice(self) -> None:
        reason = self.void_reason.text().strip()
        if not reason:
            self.invoice_msg.setText("请填写作废原因")
            return
        try:
            row = self.api.void_invoice(self.pr_payment_id.value(), reason)
        except ApiError as e:
            self.invoice_msg.setText(f"作废失败（{e.status_code}）：{e.detail}")
            return
        self.invoice_msg.setText(f"发票 {row['invoice_no']} 已作废")
