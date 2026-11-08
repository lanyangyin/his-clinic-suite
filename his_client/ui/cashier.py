"""收费员工作站：患者建档/查询、挂号、收费/退费、打印。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
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


class CashierWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        tabs = QTabWidget()
        tabs.addTab(self._build_patient_tab(), "患者建档 / 查询")
        tabs.addTab(self._build_registration_tab(), "挂号")
        tabs.addTab(self._build_charge_tab(), "收费 / 退费")
        tabs.addTab(self._build_print_tab(), "打印")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    # ---------- 患者 ----------
    def _build_patient_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("新建档案")
        form = QFormLayout(box)
        self.p_name = QLineEdit()
        self.p_id_number = QLineEdit()
        self.p_phone = QLineEdit()
        form.addRow("姓名", self.p_name)
        form.addRow("身份证号", self.p_id_number)
        form.addRow("电话", self.p_phone)
        create_btn = QPushButton("建档")
        create_btn.clicked.connect(self._create_patient)
        form.addRow("", create_btn)
        layout.addWidget(box)

        query_box = QGroupBox("查询患者")
        query_layout = QHBoxLayout(query_box)
        self.q_name = QLineEdit()
        self.q_name.setPlaceholderText("姓名（可空）")
        self.q_id_number = QLineEdit()
        self.q_id_number.setPlaceholderText("身份证号（可空）")
        query_btn = QPushButton("查询")
        query_btn.clicked.connect(self._query_patients)
        query_layout.addWidget(self.q_name)
        query_layout.addWidget(self.q_id_number)
        query_layout.addWidget(query_btn)
        layout.addWidget(query_box)

        self.patient_table = QTableWidget(0, 4)
        self.patient_table.setHorizontalHeaderLabels(["ID", "姓名", "身份证号", "电话"])
        layout.addWidget(self.patient_table)

        self.patient_msg = QLabel("")
        self.patient_msg.setWordWrap(True)
        layout.addWidget(self.patient_msg)
        return page

    def _create_patient(self) -> None:
        name = self.p_name.text().strip()
        id_number = self.p_id_number.text().strip()
        if not name or not id_number:
            self.patient_msg.setText("姓名和身份证号必填")
            return
        try:
            patient = self.api.create_patient(name, id_number, self.p_phone.text().strip())
        except ApiError as e:
            self.patient_msg.setText(f"建档失败（{e.status_code}）：{e.detail}")
            return
        self.patient_msg.setText(f"建档成功：ID {patient['id']} {patient['name']}")
        self._query_patients()

    def _query_patients(self) -> None:
        try:
            rows = self.api.list_patients(
                name=self.q_name.text().strip() or None,
                id_number=self.q_id_number.text().strip() or None,
            )
        except ApiError as e:
            self.patient_msg.setText(f"查询失败：{e.detail}")
            return
        self.patient_table.setRowCount(len(rows))
        for row, patient in enumerate(rows):
            self.patient_table.setItem(row, 0, QTableWidgetItem(str(patient["id"])))
            self.patient_table.setItem(row, 1, QTableWidgetItem(patient["name"]))
            self.patient_table.setItem(row, 2, QTableWidgetItem(patient.get("id_number") or ""))
            self.patient_table.setItem(row, 3, QTableWidgetItem(patient.get("phone") or ""))

    # ---------- 挂号 ----------
    def _build_registration_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("现场挂号")
        form = QFormLayout(box)
        self.r_patient_id = QSpinBox()
        self.r_patient_id.setRange(1, 10_000_000)
        self.r_schedule_id = QSpinBox()
        self.r_schedule_id.setRange(0, 10_000_000)
        self.r_schedule_id.setSpecialValueText("不选排班")
        self.r_doctor_combo = QLineEdit()
        self.r_doctor_combo.setPlaceholderText("医生 ID")
        self.r_doctor_combo.setReadOnly(True)
        self.r_doctor_list = QTableWidget(0, 2)
        self.r_doctor_list.setHorizontalHeaderLabels(["医生 ID", "姓名 / 科室"])
        refresh_btn = QPushButton("刷新医生列表")
        refresh_btn.clicked.connect(self._load_doctors)
        row = QHBoxLayout()
        row.addWidget(self.r_doctor_list)
        form.addRow("患者 ID", self.r_patient_id)
        form.addRow("医生", row)
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
            doctors = self.api.list_doctors()
        except ApiError as e:
            self.reg_msg.setText(f"加载医生失败：{e.detail}")
            return
        self.r_doctor_list.setRowCount(len(doctors))
        for row, doctor in enumerate(doctors):
            self.r_doctor_list.setItem(row, 0, QTableWidgetItem(str(doctor["id"])))
            self.r_doctor_list.setItem(
                row, 1, QTableWidgetItem(f'{doctor["name"]}（科室 {doctor["department_id"]}）')
            )
        self.r_doctor_list.cellClicked.connect(self._pick_doctor)

    def _pick_doctor(self, row: int, _column: int) -> None:
        item = self.r_doctor_list.item(row, 0)
        if item:
            self.r_doctor_combo.setText(item.text())

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
        row = QHBoxLayout()
        self.c_encounter_id = QSpinBox()
        self.c_encounter_id.setRange(1, 10_000_000)
        query_btn = QPushButton("查询费用")
        query_btn.clicked.connect(self._load_charges)
        pay_btn = QPushButton("收费")
        pay_btn.clicked.connect(self._pay)
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.c_encounter_id)
        row.addWidget(query_btn)
        row.addWidget(pay_btn)
        box_layout.addLayout(row)

        method_row = QHBoxLayout()
        self.c_channel = QComboBox()
        for label, value in [
            ("现金", "cash"),
            ("微信支付", "wechat"),
            ("支付宝", "alipay"),
            ("POS 刷卡", "pos"),
            ("医保卡", "insurance_card"),
        ]:
            self.c_channel.addItem(label, value)
        self.c_auth_code = QLineEdit()
        self.c_auth_code.setPlaceholderText("付款码（微信/支付宝）")
        self.c_card_no = QLineEdit()
        self.c_card_no.setPlaceholderText("卡号/读卡返回值（POS/医保卡）")
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
        layout.addWidget(box)

        refund_box = QGroupBox("退费")
        refund_layout = QHBoxLayout(refund_box)
        self.refund_payment_id = QSpinBox()
        self.refund_payment_id.setRange(1, 10_000_000)
        refund_btn = QPushButton("退费")
        refund_btn.clicked.connect(self._refund)
        refund_layout.addWidget(QLabel("收费单 ID"))
        refund_layout.addWidget(self.refund_payment_id)
        refund_layout.addWidget(refund_btn)
        layout.addWidget(refund_box)

        self.refund_msg = QLabel("")
        layout.addWidget(self.refund_msg)
        layout.addStretch(1)
        return page

    def _update_payment_inputs(self) -> None:
        channel = self.c_channel.currentData() if hasattr(self, "c_channel") else "cash"
        self.c_auth_code.setEnabled(channel in ("wechat", "alipay"))
        self.c_card_no.setEnabled(channel in ("pos", "insurance_card"))

    def _load_charges(self) -> None:
        encounter_id = self.c_encounter_id.value()
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
            f"医保 {payment['insurance_amount']:.2f}，自费 {payment['self_pay_amount']:.2f}，"
            f"方式 {zh('payment_channel', payment.get('channel'))}"
            + (f"，交易号 {payment['channel_trade_no']}" if payment.get("channel_trade_no") else "")
        )
        self.refund_payment_id.setValue(payment["id"])
        self._load_charges()

    def _refund(self) -> None:
        try:
            payment = self.api.refund_payment(self.refund_payment_id.value())
        except ApiError as e:
            self.refund_msg.setText(f"退费失败（{e.status_code}）：{e.detail}")
            return
        self.refund_msg.setText(f"退费成功：单号 {payment['id']}，状态 {zh('payment_status', payment['status'])}")

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

        layout.addStretch(1)
        return page

