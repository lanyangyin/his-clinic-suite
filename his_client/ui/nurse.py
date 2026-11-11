"""护士工作站：门诊分诊叫号、治疗执行。"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
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
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.patient_banner import PatientBanner


class NurseWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.banner = PatientBanner()
        self.tabs = SidebarTabs()
        self.tabs.addTab(self._build_triage_tab(), "分诊叫号")
        self.tabs.addTab(self._build_treatment_tab(), "治疗执行")
        self.tabs.addTab(self._build_nursing_tab(), "输液执行")
        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        layout.addWidget(self.tabs)
        QShortcut(QKeySequence("F3"), self, activated=self._refresh_current)
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_refresh)
        self.auto_timer.start(15000)

    def _refresh_current(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._load_queue()

    def _auto_refresh(self) -> None:
        if self.isVisible() and self.tabs.currentIndex() == 0:
            self._load_queue()

    # ---------- 分诊 ----------
    def _build_triage_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("预检分诊登记")
        grid = QGridLayout(box)
        self.triage_reg_id = QSpinBox()
        self.triage_reg_id.setRange(1, 10_000_000)
        self.triage_level = QComboBox()
        for value, label in (
            (1, "1 级 濒危"), (2, "2 级 危重"), (3, "3 级 急症"), (4, "4 级 非急症")
        ):
            self.triage_level.addItem(label, value)
        self.triage_level.setCurrentIndex(3)
        self.triage_complaint = QLineEdit()
        self.triage_complaint.setPlaceholderText("主诉，如 胸闷气促 2 小时")
        self.triage_temp = QLineEdit()
        self.triage_temp.setPlaceholderText("℃")
        self.triage_pulse = QLineEdit()
        self.triage_pulse.setPlaceholderText("次/分")
        self.triage_resp = QLineEdit()
        self.triage_resp.setPlaceholderText("次/分")
        self.triage_sbp = QLineEdit()
        self.triage_sbp.setPlaceholderText("收缩压")
        self.triage_dbp = QLineEdit()
        self.triage_dbp.setPlaceholderText("舒张压")
        self.triage_spo2 = QLineEdit()
        self.triage_spo2.setPlaceholderText("%")
        self.triage_pain = QLineEdit()
        self.triage_pain.setPlaceholderText("0–10")
        self.triage_isolation = QCheckBox("隔离/传染病提示")
        submit = QPushButton("登记分诊")
        submit.clicked.connect(self._create_ticket)

        grid.addWidget(QLabel("挂号 ID*"), 0, 0)
        grid.addWidget(self.triage_reg_id, 0, 1)
        grid.addWidget(QLabel("分诊级别*"), 0, 2)
        grid.addWidget(self.triage_level, 0, 3)
        grid.addWidget(QLabel("主诉*"), 0, 4)
        grid.addWidget(self.triage_complaint, 0, 5, 1, 3)
        grid.addWidget(QLabel("体温*"), 1, 0)
        grid.addWidget(self.triage_temp, 1, 1)
        grid.addWidget(QLabel("脉搏*"), 1, 2)
        grid.addWidget(self.triage_pulse, 1, 3)
        grid.addWidget(QLabel("呼吸*"), 1, 4)
        grid.addWidget(self.triage_resp, 1, 5)
        grid.addWidget(QLabel("SpO2*"), 1, 6)
        grid.addWidget(self.triage_spo2, 1, 7)
        grid.addWidget(QLabel("血压*"), 2, 0)
        grid.addWidget(self.triage_sbp, 2, 1)
        grid.addWidget(QLabel("/"), 2, 2)
        grid.addWidget(self.triage_dbp, 2, 3)
        grid.addWidget(QLabel("疼痛评分"), 2, 4)
        grid.addWidget(self.triage_pain, 2, 5)
        grid.addWidget(self.triage_isolation, 2, 6, 1, 2)
        grid.addWidget(submit, 3, 7)
        layout.addWidget(box)

        queue_row = QHBoxLayout()
        refresh = QPushButton("刷新队列")
        refresh.clicked.connect(self._load_queue)
        call = QPushButton("叫号")
        call.clicked.connect(self._call_ticket)
        skip = QPushButton("过号")
        skip.clicked.connect(self._pass_ticket)
        queue_row.addWidget(refresh)
        queue_row.addWidget(call)
        queue_row.addWidget(skip)
        queue_row.addStretch(1)
        layout.addLayout(queue_row)

        self.queue_table = QTableWidget(0, 7)
        self.queue_table.setHorizontalHeaderLabels(
            ["叫号单", "挂号", "级别", "体温", "血压", "SpO2", "状态"]
        )
        self.queue_table.cellClicked.connect(self._select_ticket_patient)
        layout.addWidget(self.queue_table)

        self.triage_patient = QLabel("")
        self.triage_patient.setWordWrap(True)
        layout.addWidget(self.triage_patient)

        self.triage_msg = QLabel("")
        self.triage_msg.setWordWrap(True)
        layout.addWidget(self.triage_msg)
        return page

    def _selected_ticket_id(self) -> int | None:
        row = self.queue_table.currentRow()
        if row < 0:
            return None
        item = self.queue_table.item(row, 0)
        return int(item.text()) if item else None

    def _select_ticket_patient(self, row: int, _col: int) -> None:
        reg_item = self.queue_table.item(row, 1)
        if not reg_item:
            return
        try:
            registration = self.api.get_registration(int(reg_item.text()))
            patient = self.api.get_patient(registration["patient_id"])
        except (ApiError, KeyError, ValueError) as e:
            detail = e.detail if isinstance(e, ApiError) else str(e)
            self.triage_patient.setText(f"患者信息加载失败：{detail}")
            return
        gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "不详")
        age = patient.get("age")
        allergy = patient.get("allergy_label") or "不详"
        self.banner.set_patient(patient, status=f"分诊 {self.queue_table.item(row, 2).text()}")
        self.triage_patient.setText(
            f"患者：{patient.get('patient_no') or patient['id']} {patient['name']} · "
            f"{gender}/{age if age is not None else '—'}岁 · 过敏：{allergy} · "
            f"分诊：{self.queue_table.item(row, 2).text()} · "
            f"体温 {self.queue_table.item(row, 3).text()} · "
            f"血压 {self.queue_table.item(row, 4).text()} · "
            f"SpO2 {self.queue_table.item(row, 5).text()}"
        )
        if patient.get("allergy_status") == "present":
            self.triage_patient.setStyleSheet("color:#b91c1c;font-weight:bold")
        else:
            self.triage_patient.setStyleSheet("")

    def _parse_number(self, field: QLineEdit, label: str, cast=float):
        text = field.text().strip()
        if not text:
            raise ValueError(f"请填写{label}")
        try:
            return cast(text)
        except ValueError:
            raise ValueError(f"{label}必须是数字") from None

    def _create_ticket(self) -> None:
        try:
            temperature = self._parse_number(self.triage_temp, "体温")
            pulse = self._parse_number(self.triage_pulse, "脉搏", int)
            respiration = self._parse_number(self.triage_resp, "呼吸", int)
            systolic = self._parse_number(self.triage_sbp, "收缩压", int)
            diastolic = self._parse_number(self.triage_dbp, "舒张压", int)
            spo2 = self._parse_number(self.triage_spo2, "SpO2", int)
        except ValueError as e:
            self.triage_msg.setText(str(e))
            return
        if not self.triage_complaint.text().strip():
            self.triage_msg.setText("请填写主诉")
            return
        pain_text = self.triage_pain.text().strip()
        payload = {
            "triage_level": self.triage_level.currentData(),
            "chief_complaint": self.triage_complaint.text().strip(),
            "temperature": temperature,
            "pulse": pulse,
            "respiration": respiration,
            "systolic": systolic,
            "diastolic": diastolic,
            "spo2": spo2,
            "pain_score": int(pain_text) if pain_text else None,
            "isolation": self.triage_isolation.isChecked(),
        }
        try:
            ticket = self.api.create_triage_ticket(self.triage_reg_id.value(), payload)
        except ApiError as e:
            self.triage_msg.setText(f"分诊失败（{e.status_code}）：{e.detail}")
            return
        self.triage_msg.setText(
            f"分诊成功：叫号单 {ticket['id']}，{ticket['triage_level']} 级，"
            f"{ticket.get('vital_summary') or ''}"
        )
        self._load_queue()

    def _load_queue(self) -> None:
        try:
            tickets = self.api.triage_queue()
        except ApiError as e:
            self.triage_msg.setText(f"加载队列失败：{e.detail}")
            return
        self.queue_table.setRowCount(len(tickets))
        for row, ticket in enumerate(tickets):
            values = [
                str(ticket["id"]),
                str(ticket["registration_id"]),
                f"{ticket.get('triage_level') or 4} 级",
                f"{ticket['temperature']:g}℃" if ticket.get("temperature") is not None else "—",
                ticket.get("bp_display") or "—",
                f"{ticket['spo2']}%" if ticket.get("spo2") is not None else "—",
                zh("ticket_status", ticket["status"]),
            ]
            for col, value in enumerate(values):
                self.queue_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.triage_msg.setText(f"当前队列 {len(tickets)} 人")

    def _call_ticket(self) -> None:
        ticket_id = self._selected_ticket_id()
        if not ticket_id:
            self.triage_msg.setText("请先在队列中选中一条记录")
            return
        try:
            ticket = self.api.call_ticket(ticket_id)
        except ApiError as e:
            self.triage_msg.setText(f"叫号失败（{e.status_code}）：{e.detail}")
            return
        self.triage_msg.setText(f"已叫号：{ticket['id']}（{zh('ticket_status', ticket['status'])}）")
        self._load_queue()

    def _pass_ticket(self) -> None:
        ticket_id = self._selected_ticket_id()
        if not ticket_id:
            self.triage_msg.setText("请先在队列中选中一条记录")
            return
        try:
            ticket = self.api.pass_ticket(ticket_id)
        except ApiError as e:
            self.triage_msg.setText(f"过号失败（{e.status_code}）：{e.detail}")
            return
        self.triage_msg.setText(f"已过号：{ticket['id']}（{zh('ticket_status', ticket['status'])}）")
        self._load_queue()

    # ---------- 治疗执行 ----------
    def _build_treatment_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        refresh = QPushButton("刷新待执行治疗")
        refresh.clicked.connect(self._load_pending_treatments)
        execute = QPushButton("执行选中治疗")
        execute.clicked.connect(self._execute_treatment)
        row.addWidget(refresh)
        row.addWidget(execute)
        row.addStretch(1)
        layout.addLayout(row)

        self.treat_table = QTableWidget(0, 5)
        self.treat_table.setHorizontalHeaderLabels(
            ["治疗单 ID", "就诊 ID", "项目", "数量", "状态"]
        )
        layout.addWidget(self.treat_table)

        self.treat_msg = QLabel("")
        self.treat_msg.setWordWrap(True)
        layout.addWidget(self.treat_msg)
        return page

    def _load_pending_treatments(self) -> None:
        try:
            orders = self.api.list_pending_treatments()
        except ApiError as e:
            self.treat_msg.setText(f"加载治疗单失败：{e.detail}")
            return
        self.treat_table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            self.treat_table.setItem(row, 0, QTableWidgetItem(str(order["id"])))
            self.treat_table.setItem(
                row, 1, QTableWidgetItem(str(order["encounter_id"]))
            )
            self.treat_table.setItem(row, 2, QTableWidgetItem(order["item_name"]))
            self.treat_table.setItem(row, 3, QTableWidgetItem(str(order["quantity"])))
            self.treat_table.setItem(row, 4, QTableWidgetItem(zh('treatment_status', order["status"])))
        self.treat_msg.setText(f"待执行治疗单 {len(orders)} 条")

    def _execute_treatment(self) -> None:
        row = self.treat_table.currentRow()
        if row < 0:
            self.treat_msg.setText("请先选中一条治疗单")
            return
        order_id = int(self.treat_table.item(row, 0).text())
        try:
            order = self.api.execute_treatment(order_id)
        except ApiError as e:
            self.treat_msg.setText(f"执行失败（{e.status_code}）：{e.detail}")
            return
        self.treat_msg.setText(
            f"已执行：{order['item_name']}（执行人 {order.get('executed_by') or '—'}）"
        )
        self._load_pending_treatments()


    # ---------- 输液/医嘱执行 ----------
    def _build_nursing_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        top = QHBoxLayout()
        self.nurse_encounter_id = QSpinBox()
        self.nurse_encounter_id.setRange(1, 10_000_000)
        sync = QPushButton("同步医嘱")
        sync.clicked.connect(self._sync_nursing)
        refresh = QPushButton("刷新执行单")
        refresh.clicked.connect(self._load_nursing)
        self.nursing_filter = QComboBox()
        for label, value in [
            ("未完成", "pending,prepared,executing"),
            ("待配药", "pending"),
            ("已配药", "prepared"),
            ("执行中", "executing"),
            ("全部", None),
        ]:
            self.nursing_filter.addItem(label, value)
        top.addWidget(QLabel("就诊 ID"))
        top.addWidget(self.nurse_encounter_id)
        top.addWidget(sync)
        top.addWidget(refresh)
        top.addWidget(self.nursing_filter)
        layout.addLayout(top)

        self.nursing_table = QTableWidget(0, 9)
        self.nursing_table.setHorizontalHeaderLabels(
            ["患者", "项目", "类型", "用法", "状态", "座位", "滴速", "执行单", "高危"]
        )
        self.nursing_table.cellClicked.connect(self._select_nursing)
        layout.addWidget(self.nursing_table, 1)

        prep_box = QGroupBox("配药")
        prep = QFormLayout(prep_box)
        self.solvent = QLineEdit()
        self.solvent.setPlaceholderText("如 0.9%氯化钠 250ml")
        self.dose = QLineEdit()
        self.dose.setPlaceholderText("如 1g")
        self.batch_no = QLineEdit()
        self.batch_no.setPlaceholderText("药品批号")
        self.checked_by = QLineEdit()
        self.checked_by.setPlaceholderText("核对人")
        prep_btn = QPushButton("配药完成")
        prep_btn.clicked.connect(self._prepare_nursing)
        prep.addRow("溶媒", self.solvent)
        prep.addRow("剂量", self.dose)
        prep.addRow("批号", self.batch_no)
        prep.addRow("核对人", self.checked_by)
        prep.addRow("", prep_btn)
        layout.addWidget(prep_box)

        exec_box = QGroupBox("执行 / 巡视")
        form = QFormLayout(exec_box)
        row = QHBoxLayout()
        self.seat_no = QLineEdit()
        self.seat_no.setPlaceholderText("输液座位号")
        self.rate = QLineEdit()
        self.rate.setPlaceholderText("滴速 ml/h")
        row.addWidget(QLabel("座位"))
        row.addWidget(self.seat_no)
        row.addWidget(QLabel("滴速"))
        row.addWidget(self.rate)
        self.nursing_note = QLineEdit()
        self.nursing_note.setPlaceholderText("巡视/完成/跳过说明")
        self.adverse = QLineEdit()
        self.adverse.setPlaceholderText("不良反应，没有可留空")
        form.addRow(row)
        form.addRow("说明", self.nursing_note)
        form.addRow("不良反应", self.adverse)
        buttons = QHBoxLayout()
        start = QPushButton("开始执行")
        start.clicked.connect(self._start_nursing)
        observe = QPushButton("巡视记录")
        observe.clicked.connect(self._observe_nursing)
        complete = QPushButton("完成")
        complete.clicked.connect(self._complete_nursing)
        skip = QPushButton("跳过")
        skip.clicked.connect(self._skip_nursing)
        buttons.addWidget(start)
        buttons.addWidget(observe)
        buttons.addWidget(complete)
        buttons.addWidget(skip)
        form.addRow(buttons)
        layout.addWidget(exec_box)

        self.nursing_msg = QLabel("")
        self.nursing_msg.setWordWrap(True)
        layout.addWidget(self.nursing_msg)
        return page

    def _sync_nursing(self) -> None:
        try:
            created = self.api.sync_nursing(self.nurse_encounter_id.value())
        except ApiError as e:
            self.nursing_msg.setText(f"同步失败（{e.status_code}）：{e.detail}")
            return
        self.nursing_msg.setText(f"已生成 {len(created)} 条新执行单")
        self._load_nursing()

    def _load_nursing(self) -> None:
        try:
            self.nursing_rows = self.api.list_nursing_orders(
                self.nursing_filter.currentData()
            )
        except ApiError as e:
            self.nursing_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.nursing_table.setRowCount(len(self.nursing_rows))
        for row, order in enumerate(self.nursing_rows):
            values = [
                order.get("patient_name") or "",
                order["item_name"],
                {"infusion": "输液", "injection": "注射", "treatment": "治疗"}.get(
                    order["order_type"], order["order_type"]
                ),
                f"{order.get('dosage') or ''} {order.get('route') or ''}".strip() or "—",
                {
                    "pending": "待配药",
                    "prepared": "已配药",
                    "executing": "执行中",
                    "completed": "已完成",
                    "skipped": "已跳过",
                }.get(order["status"], order["status"]),
                order.get("seat_no") or "—",
                f"{order['rate_ml_h']:g}" if order.get("rate_ml_h") else "—",
                str(order["id"]),
                "是" if order.get("high_alert") else "",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if order.get("high_alert"):
                    cell.setForeground(Qt.red)
                self.nursing_table.setItem(row, col, cell)
        self.nursing_msg.setText(f"执行单 {len(self.nursing_rows)} 条")

    def _select_nursing(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.nursing_rows):
            self.current_nursing = self.nursing_rows[row]
            self.nursing_msg.setText(
                f"当前：{self.current_nursing['item_name']} · "
                f"{self.current_nursing['status']}"
                + (" · 高危药品需双人核对" if self.current_nursing.get("high_alert") else "")
            )

    def _selected_nursing(self) -> dict | None:
        order = getattr(self, "current_nursing", None)
        if not order:
            self.nursing_msg.setText("请先选择一条执行单")
        return order

    def _prepare_nursing(self) -> None:
        order = self._selected_nursing()
        if not order:
            return
        try:
            self.api.prepare_nursing(
                order["id"],
                {
                    "solvent": self.solvent.text().strip(),
                    "dose": self.dose.text().strip(),
                    "batch_no": self.batch_no.text().strip(),
                    "checked_by": self.checked_by.text().strip(),
                    "expires_minutes": 120,
                },
            )
        except ApiError as e:
            self.nursing_msg.setText(f"配药失败（{e.status_code}）：{e.detail}")
            return
        self.nursing_msg.setText("配药完成")
        self._load_nursing()

    def _rate_value(self) -> float | None:
        text = self.rate.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _start_nursing(self) -> None:
        order = self._selected_nursing()
        if not order:
            return
        try:
            self.api.start_nursing(
                order["id"],
                {"seat_no": self.seat_no.text().strip(), "rate_ml_h": self._rate_value()},
            )
        except ApiError as e:
            self.nursing_msg.setText(f"开始失败（{e.status_code}）：{e.detail}")
            return
        self.nursing_msg.setText("已开始执行")
        self._load_nursing()

    def _observe_nursing(self) -> None:
        order = self._selected_nursing()
        if not order:
            return
        try:
            self.api.observe_nursing(
                order["id"],
                {
                    "rate_ml_h": self._rate_value(),
                    "note": self.nursing_note.text().strip(),
                    "adverse_reaction": self.adverse.text().strip(),
                },
            )
        except ApiError as e:
            self.nursing_msg.setText(f"巡视失败（{e.status_code}）：{e.detail}")
            return
        self.nursing_msg.setText("巡视已记录")
        self._load_nursing()

    def _complete_nursing(self) -> None:
        order = self._selected_nursing()
        if not order:
            return
        try:
            self.api.complete_nursing(
                order["id"],
                {
                    "note": self.nursing_note.text().strip(),
                    "adverse_reaction": self.adverse.text().strip(),
                },
            )
        except ApiError as e:
            self.nursing_msg.setText(f"完成失败（{e.status_code}）：{e.detail}")
            return
        self.nursing_msg.setText("执行完成")
        self._load_nursing()

    def _skip_nursing(self) -> None:
        order = self._selected_nursing()
        if not order:
            return
        reason = self.nursing_note.text().strip()
        if not reason:
            self.nursing_msg.setText("请在说明中填写跳过原因")
            return
        try:
            self.api.skip_nursing(order["id"], reason)
        except ApiError as e:
            self.nursing_msg.setText(f"跳过失败（{e.status_code}）：{e.detail}")
            return
        self.nursing_msg.setText("已跳过")
        self._load_nursing()
