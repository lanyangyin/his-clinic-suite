"""门诊工作站：叫号接诊、结构化病历、开方（含用法）、检验检查开单、治疗开单。"""
from PySide6.QtCore import Qt, QTimer, QUrl
from datetime import datetime
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QCompleter,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QSizePolicy,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme
from his_client.config import load_config
from his_client.labels import zh
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.patient_banner import PatientBanner
from his_client.ui.adverse_reaction_dialog import AdverseReactionDialog
from his_client.ui.patient_info_panel import PatientInfoPanel
from his_client.ui.payment import PaymentPanel

_RECORD_FIELDS = [
    ("chief_complaint", "主诉", 200),
    ("present_illness", "现病史", 1000),
    ("past_history", "既往史", 1000),
    ("personal_history", "个人史", 1000),
    ("marital_history", "婚育史", 1000),
    ("family_history", "家族史", 1000),
    ("physical_exam", "体格检查", 1000),
    ("auxiliary_exam", "辅助检查", 1000),
    ("treatment_advice", "处理意见", 500),
]


class DoctorWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.insurance_enabled = load_config().insurance_enabled
        self.banner = PatientBanner()
        self.tabs = SidebarTabs()
        self.tabs.addTab(self._build_workbench_tab(), "门诊工作台")
        self.tabs.addTab(self._build_register_tab(), "挂号")
        self.tabs.addTab(self._build_reception_tab(), "接诊")
        self.tabs.addTab(self._build_record_tab(), "病历")
        self.tabs.addTab(self._build_history_tab(), "历史诊疗")
        self.tabs.addTab(self._build_prescription_tab(), "开方")
        self.payment_panel = PaymentPanel(api)
        self.tabs.addTab(self.payment_panel, "收费")
        self.tabs.addTab(self._build_exam_tab(), "检验 / 检查")
        self.tabs.addTab(self._build_treatment_tab(), "治疗")
        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        body = QHBoxLayout()
        self.side_panel = QWidget()
        self.side_panel.setFixedWidth(300)
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(0, 0, 8, 0)
        self.side_info = PatientInfoPanel()
        side_layout.addWidget(self.side_info)
        history_row = QHBoxLayout()
        history_title = QLabel("历史就诊")
        history_title.setStyleSheet("font-weight:bold;margin-top:6px")
        history_refresh = QPushButton("刷新")
        history_refresh.clicked.connect(self._refresh_side_history)
        history_row.addWidget(history_title)
        history_row.addStretch(1)
        history_row.addWidget(history_refresh)
        side_layout.addLayout(history_row)
        self.side_history = QTableWidget(0, 3)
        self.side_history.setHorizontalHeaderLabels(["日期", "诊断", "医生"])
        self.side_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.side_history.verticalHeader().setVisible(False)
        self.side_history.cellDoubleClicked.connect(self._open_side_history)
        side_layout.addWidget(self.side_history, 1)
        self.side_history_msg = QLabel("")
        self.side_history_msg.setWordWrap(True)
        self.side_history_msg.setStyleSheet("")
        side_layout.addWidget(self.side_history_msg)
        body.addWidget(self.side_panel)
        body.addWidget(self.tabs, 1)
        layout.addLayout(body)
        self._load_diagnoses()
        self._install_shortcuts()
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_refresh)
        self.auto_timer.start(15000)
        self.side_panel.setFixedWidth(0)
        self.side_panel.setVisible(False)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, _index: int) -> None:
        if hasattr(self, "side_panel"):
            if _index == 0:
                self.side_panel.setFixedWidth(0)
                self.side_panel.setVisible(False)
            else:
                self.side_panel.setFixedWidth(300)
                self.side_panel.setVisible(True)
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
        splitter = QSplitter(Qt.Horizontal)

        # 左栏：搜索 + 状态页签 + 患者队列（统计并入页签）
        queue = QWidget()
        queue_layout = QVBoxLayout(queue)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        queue_title = QLabel(f"门诊队列 · {datetime.now():%Y-%m-%d}")
        queue_title.setStyleSheet("font-size:15px;font-weight:bold;")
        self.wb_search = QLineEdit()
        self.wb_search.setPlaceholderText("F2 搜索姓名/电话/挂号号")
        self.wb_search.setClearButtonEnabled(True)
        self.wb_search.textChanged.connect(self._filter_workbench)
        refresh = QPushButton("刷新")
        refresh.setFixedWidth(64)
        refresh.clicked.connect(self._load_workbench)
        top.addWidget(queue_title)
        top.addWidget(self.wb_search, 1)
        top.addWidget(refresh)
        queue_layout.addLayout(top)

        self.wb_status_tabs = QTabBar()
        for label in ("全部", "待接诊", "接诊中", "已挂起", "已收费"):
            self.wb_status_tabs.addTab(label)
        self.wb_status_tabs.currentChanged.connect(self._filter_workbench)
        queue_layout.addWidget(self.wb_status_tabs)

        self.wb_table = QTableWidget(0, 7)
        self.wb_table.setHorizontalHeaderLabels(
            ["挂号", "患者", "医生", "挂号状态", "就诊", "诊断", "待缴"]
        )
        self.wb_table.cellClicked.connect(self._select_workbench)
        self.wb_table.cellDoubleClicked.connect(
            lambda row, _col: self._start_workbench_row(row)
        )
        self.wb_table.setAlternatingRowColors(True)
        queue_layout.addWidget(self.wb_table, 1)
        splitter.addWidget(queue)

        # 右栏：患者信息 + 危急值 + 操作 + 费用
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.patient_info = PatientInfoPanel()
        self.patient_info.setMaximumWidth(16777215)
        self.patient_info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_layout.addWidget(self.patient_info)
        self.wb_patient = QLabel("请选择患者")
        self.wb_patient.setWordWrap(True)
        self.wb_patient.setVisible(False)

        critical_box = QGroupBox("危急值待确认")
        critical_layout = QVBoxLayout(critical_box)
        self.critical_table = QTableWidget(0, 5)
        self.critical_table.setHorizontalHeaderLabels(
            ["患者", "项目", "结果", "报告时间", "超时"]
        )
        self.critical_table.setMaximumHeight(90)
        self.critical_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
        right_layout.addWidget(critical_box)

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
        row.addWidget(self.wb_diagnosis, 1)
        row.addWidget(self.wb_start)
        right_layout.addLayout(row)

        actions = QGridLayout()
        self.wb_action_buttons = {}
        for index, (text, handler) in enumerate(
            [
                ("写病历", self._wb_record),
                ("开方", self._wb_prescribe),
                ("开检验", self._wb_exam),
                ("开治疗", self._wb_treat),
                ("历史诊疗", self._wb_history),
                ("挂起当前", self._pause_workbench),
                ("继续接诊", self._resume_workbench),
                ("药物反应 / 换药", self._adverse_reaction),
            ]
        ):
            button = QPushButton(text)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(handler)
            self.wb_action_buttons[text] = button
            actions.addWidget(button, index // 3, index % 3)
        right_layout.addLayout(actions)

        self.wb_summary = QLabel("")
        self.wb_summary.setWordWrap(True)
        right_layout.addWidget(self.wb_summary)
        self.wb_fee_table = QTableWidget(0, 4)
        self.wb_fee_table.setHorizontalHeaderLabels(["项目", "数量", "金额", "状态"])
        self.wb_fee_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.wb_fee_table, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([800, 520])
        layout.addWidget(splitter, 1)
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
        all_rows = getattr(self, "workbench_all", getattr(self, "workbench_rows", []))
        index = self.wb_status_tabs.currentIndex() if hasattr(self, "wb_status_tabs") else 0
        status_filter = {
            1: "waiting",
            2: "open",
            3: "paused",
            4: "closed",
        }.get(index, "")
        if status_filter == "waiting":
            rows = [item for item in all_rows if not item.get("encounter_id")]
        elif status_filter:
            rows = [
                item for item in all_rows
                if (item.get("encounter_status") or "") == status_filter
            ]
        else:
            rows = list(all_rows)
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
                (
                    f"{item.get('encounter_id')} "
                    f"{ {'open':'进行中','paused':'已挂起','closed':'已收费'}.get(item.get('encounter_status'), item.get('encounter_status') or '') }".strip()
                    if item.get("encounter_id") else "—"
                ),
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
            f"显示 {len(rows)} / 今日 {total} 人" if term or status_filter else f"今日队列 {total} 人"
        )
        waiting = sum(1 for item in all_rows if not item.get("encounter_id"))
        open_count = sum(1 for item in all_rows if item.get("encounter_status") == "open")
        paused_count = sum(1 for item in all_rows if item.get("encounter_status") == "paused")
        closed_count = sum(1 for item in all_rows if item.get("encounter_status") == "closed")
        if hasattr(self, "wb_status_tabs"):
            for index, (label, count) in enumerate(
                zip(
                    ("全部", "待接诊", "接诊中", "已挂起", "已收费"),
                    (total, waiting, open_count, paused_count, closed_count),
                )
            ):
                self.wb_status_tabs.setTabText(index, f"{label} {count}")
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
            self.critical_msg.setStyleSheet("color:#ef4444;font-weight:bold")
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
        patient = {
            "id": item.get("patient_id"),
            "patient_no": item.get("patient_no"),
            "name": item.get("patient_name"),
            "gender": item.get("gender"),
            "age": item.get("age"),
            "allergy_label": item.get("allergy_label"),
            "special_history": item.get("special_history"),
            "phone": item.get("phone"),
        }
        status = "已接诊" if item.get("encounter_id") else "待接诊"
        self.banner.set_patient(patient, item.get("encounter_id"), status)
        self.patient_info.set_patient(
            patient,
            item.get("encounter_id"),
            status,
            f"分诊：{item.get('triage_level') or '—'} 级\n"
            f"生命体征：{item.get('vital_summary') or '未测'}",
        )
        self.side_info.set_patient(
            patient,
            item.get("encounter_id"),
            status,
            f"分诊：{item.get('triage_level') or '—'} 级\n"
            f"生命体征：{item.get('vital_summary') or '未测'}",
        )
        self._load_side_history(item.get("patient_id"))
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
            self.wb_patient.setStyleSheet("color:#ef4444;font-weight:bold")
        elif item.get("allergy_label") not in (None, "", "无过敏史", "过敏史不详"):
            self.wb_patient.setStyleSheet("color:#ef4444;font-weight:bold")
        else:
            self.wb_patient.setStyleSheet("")
        self.wb_diagnosis.setText(item.get("diagnosis") or "")
        code_index = self.wb_diagnosis_code.findData(item.get("diagnosis_code") or "")
        if code_index >= 0:
            self.wb_diagnosis_code.blockSignals(True)
            self.wb_diagnosis_code.setCurrentIndex(code_index)
            self.wb_diagnosis_code.blockSignals(False)
        status = item.get("encounter_status") or ""
        self.wb_start.setEnabled(not item.get("encounter_id") or status == "paused")
        if hasattr(self, "wb_action_buttons"):
            self.wb_action_buttons["挂起当前"].setEnabled(status == "open")
            self.wb_action_buttons["继续接诊"].setEnabled(status == "paused")
            self.wb_action_buttons["药物反应 / 换药"].setEnabled(bool(item.get("encounter_id")))
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
            if item.get("encounter_status") == "paused" and item.get("encounter_id"):
                encounter = self.api.resume_encounter(item["encounter_id"])
            else:
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
        patient = {
            "id": item.get("patient_id"),
            "patient_no": item.get("patient_no"),
            "name": item.get("patient_name"),
            "gender": item.get("gender"),
            "age": item.get("age"),
            "allergy_label": item.get("allergy_label"),
            "special_history": item.get("special_history"),
            "phone": item.get("phone"),
        }
        self.banner.set_patient(patient, encounter["id"], "已接诊")
        self.patient_info.set_patient(
            patient, encounter["id"], "已接诊",
            f"诊断：{self.wb_diagnosis.text().strip() or '—'}",
        )
        self.side_info.set_patient(
            patient, encounter["id"], "已接诊", f"诊断：{self.wb_diagnosis.text().strip() or '—'}"
        )
        self._side_history_patient_id = None
        self._load_side_history(item.get("patient_id"))

    def _pause_workbench(self) -> None:
        item = getattr(self, "wb_current", None)
        if not item or not item.get("encounter_id"):
            self.wb_summary.setText("请先选择一个已接诊患者")
            return
        try:
            self.api.pause_encounter(item["encounter_id"])
        except ApiError as e:
            self.wb_summary.setText(f"挂起失败（{e.status_code}）：{e.detail}")
            return
        self.wb_summary.setText("已挂起当前患者；现在可以开始下一位，之后从队列继续接诊")
        self._load_workbench()

    def _resume_workbench(self) -> None:
        item = getattr(self, "wb_current", None)
        if not item or not item.get("encounter_id"):
            self.wb_summary.setText("请先选择一个已挂起患者")
            return
        try:
            self.api.resume_encounter(item["encounter_id"])
        except ApiError as e:
            self.wb_summary.setText(f"继续接诊失败（{e.status_code}）：{e.detail}")
            return
        self._load_workbench()
        for row, candidate in enumerate(self.workbench_rows):
            if candidate["registration_id"] == item["registration_id"]:
                self.wb_table.selectRow(row)
                self._select_workbench(row, 0)
                break

    def _adverse_reaction(self) -> None:
        item = getattr(self, "wb_current", None)
        if not item or not item.get("encounter_id"):
            self.wb_summary.setText("请先选择当前接诊患者")
            return
        dialog = AdverseReactionDialog(item.get("patient_name") or "", self)
        if dialog.exec() != dialog.Accepted:
            return
        payload = dialog.payload()
        if not payload["reaction"]:
            self.wb_summary.setText("请填写药物反应表现")
            return
        try:
            self.api.record_adverse_reaction(item["encounter_id"], payload)
        except ApiError as e:
            self.wb_summary.setText(f"记录失败（{e.status_code}）：{e.detail}")
            return
        QMessageBox.information(
            self,
            "药物反应已记录",
            "就诊已挂起，未执行护理单已停止。\n\n下一步：\n"
            "1. 护士核对并停止输液/治疗\n"
            "2. 药房按退药流程回补未用药品\n"
            "3. 收费按退费规则处理\n"
            "4. 医生重新开方、收费后继续治疗",
        )
        self._load_workbench()

    def _switch_tab(self, text: str) -> None:
        for index in range(self.tabs.count()):
            if text in self.tabs.tabText(index):
                self.tabs.setCurrentIndex(index)
                return

    def _load_side_history(self, patient_id: int | None) -> None:
        if not patient_id:
            self.side_history.setRowCount(0)
            self.side_history_msg.setText("")
            self._side_history_patient_id = None
            return
        if getattr(self, "_side_history_patient_id", None) == patient_id:
            return
        self._side_history_patient_id = patient_id
        try:
            data = self.api.get_patient_history(patient_id)
        except ApiError as e:
            self.side_history.setRowCount(0)
            self.side_history_msg.setText(f"历史加载失败：{e.detail}")
            return
        encounters = data.get("encounters") or []
        self.side_history_data = encounters
        self.side_history.setRowCount(len(encounters))
        for row, encounter in enumerate(encounters):
            values = [
                str(encounter.get("visited_at") or "")[:10],
                f"{encounter.get('diagnosis_code') or ''} {encounter.get('diagnosis') or ''}".strip() or "—",
                encounter.get("doctor_name") or "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.side_history.setItem(row, col, item)
        self.side_history_msg.setText(
            f"共 {len(encounters)} 次；双击一行查看完整历史"
        )

    def _refresh_side_history(self) -> None:
        self._side_history_patient_id = None
        patient_id = getattr(self, "side_info", None).patient_id
        if patient_id:
            self._load_side_history(patient_id)

    def _open_side_history(self, row: int, _col: int) -> None:
        data = getattr(self, "side_history_data", None)
        if not data or not (0 <= row < len(data)):
            return
        target_id = data[row].get("id")
        self._switch_tab("历史诊疗")
        patient_id = getattr(self, "side_info", None).patient_id
        if not patient_id:
            return
        self._load_history(patient_id)
        for index, encounter in enumerate(getattr(self, "history_data", {}).get("encounters", [])):
            if encounter.get("id") == target_id:
                self.history_enc_table.selectRow(index)
                self._history_select(index, 0)
                break

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
        if hasattr(self, "exam_table"):
            self._refresh_exam_requests()
        if hasattr(self, "treat_table"):
            self._refresh_treatments()
        if not hasattr(self, "side_info"):
            return
        if not encounter_id:
            return
        try:
            summary = self.api.encounter_summary(encounter_id)
        except ApiError:
            return
        self.side_info.set_patient(
            {
                "id": summary.get("patient_id"),
                "patient_no": summary.get("patient_no"),
                "name": summary.get("patient_name"),
                "gender": summary.get("gender"),
                "age": summary.get("age"),
                "allergy_label": summary.get("allergy_label"),
                "special_history": summary.get("special_history"),
                "phone": summary.get("phone"),
            },
            encounter_id,
            {"open": "接诊中", "paused": "已挂起", "closed": "已收费"}.get(
                summary.get("status") or "", summary.get("status") or ""
            ),
        )
        self._load_side_history(summary.get("patient_id"))

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
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
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
        search_layout.addWidget(self.reg_patient_table, 1)
        left_layout.addWidget(search_box, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        box = QGroupBox("现场挂号")
        form = QFormLayout(box)
        self.reg_patient_id = QLineEdit()
        self.reg_patient_id.setReadOnly(True)
        self.reg_patient_id.setPlaceholderText("在左侧选择患者")
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
        right_layout.addWidget(box)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 380])
        layout.addWidget(splitter, 1)

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
        self.record_diagnosis = QLabel("诊断：—")
        self.record_diagnosis.setStyleSheet("font-weight:bold")
        top.addWidget(self.record_diagnosis, 1)
        layout.addLayout(top)

        self.record_edits: dict[str, QTextEdit] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        positions = {
            "chief_complaint": (0, 0),
            "present_illness": (0, 1),
            "past_history": (1, 0),
            "personal_history": (1, 1),
            "marital_history": (2, 0),
            "family_history": (2, 1),
            "physical_exam": (3, 0),
            "auxiliary_exam": (3, 1),
            "treatment_advice": (4, 0),
        }
        for key, label, _limit in _RECORD_FIELDS:
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            edit = QTextEdit()
            placeholders = {
                "personal_history": "吸烟、饮酒、职业、居住环境等",
                "marital_history": "婚姻、生育史",
                "family_history": "家族中同类疾病/遗传病",
                "auxiliary_exam": "外院检查、既往检查结果；本次检验检查自动列在打印页",
            }
            edit.setPlaceholderText(placeholders.get(key, f"填写{label}"))
            edit.setMinimumHeight(72 if key != "treatment_advice" else 80)
            self.record_edits[key] = edit
            box_layout.addWidget(edit)
            row, col = positions[key]
            if key == "treatment_advice":
                grid.addWidget(box, row, col, 1, 2)
            else:
                grid.addWidget(box, row, col)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid, 1)

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
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.record_msg = QLabel("")
        self.record_msg.setWordWrap(True)
        layout.addWidget(self.record_msg)
        return page

    def _load_record(self) -> None:
        try:
            record = self.api.get_medical_record(self.mr_encounter_id.value())
            encounter = self.api.get_encounter(self.mr_encounter_id.value())
        except ApiError as e:
            self.record_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        if hasattr(self, "record_diagnosis"):
            self.record_diagnosis.setText(
                f"诊断：{encounter.get('diagnosis_code') or ''} "
                f"{encounter.get('diagnosis') or '—'}".strip()
            )
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
        self.history_patient_label.setStyleSheet("font-weight:bold")
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
        self.rx_form_filter = QComboBox()
        for label, value in (
            ("全部剂型", ""),
            ("口服", "口服"),
            ("注射", "注射"),
            ("外用", "外用"),
            ("其他", "其他"),
        ):
            self.rx_form_filter.addItem(label, value)
        self.rx_form_filter.currentIndexChanged.connect(self._filter_drugs)
        top.addWidget(self.rx_form_filter)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 16, 0)
        left_title = QLabel("药品目录")
        left_title.setStyleSheet("font-weight:bold")
        left_layout.addWidget(left_title)
        self.drug_table = QTableWidget(0, 8)
        self.drug_table.setHorizontalHeaderLabels(
            ["ID", "药品", "规格", "单价", "库存", "自费约", "医保比例", "医保类别"]
        )
        if not self.insurance_enabled:
            self.drug_table.setColumnHidden(6, True)
            self.drug_table.setColumnHidden(7, True)
        self.drug_table.cellClicked.connect(self._pick_drug_row)
        self.drug_table.cellDoubleClicked.connect(self._pick_drug_row)
        left_layout.addWidget(self.drug_table, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
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
        right_layout.addWidget(box)

        self.rx_msg = QLabel("")
        self.rx_msg.setWordWrap(True)
        right_layout.addWidget(self.rx_msg)

        rx_title = QLabel("本次处方")
        rx_title.setStyleSheet("font-weight:bold")
        right_layout.addWidget(rx_title)
        self.rx_table = QTableWidget(0, 5)
        self.rx_table.setHorizontalHeaderLabels(["药品", "数量", "单价", "用法", "金额"])
        self.rx_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.rx_table, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([680, 460])
        layout.addWidget(splitter, 1)

        rx_tabs = QTabWidget()
        rx_tabs.addTab(page, "西药 / 中成药 / 注射")
        rx_tabs.addTab(self._build_tcm_prescription_page(), "中药饮片")
        self.rx_type_tabs = rx_tabs
        rx_tabs.currentChanged.connect(self._on_rx_type_changed)
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(rx_tabs)
        return outer

    def _build_tcm_prescription_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        refresh = QPushButton("刷新饮片目录")
        refresh.clicked.connect(self._load_tcm_herbs)
        self.tcm_search = QLineEdit()
        self.tcm_search.setPlaceholderText("搜索饮片名称")
        self.tcm_search.setClearButtonEnabled(True)
        self.tcm_search.textChanged.connect(self._filter_tcm_herbs)
        top.addWidget(refresh)
        top.addWidget(self.tcm_search, 1)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 16, 0)
        left_title = QLabel("中药饮片目录（双击加入）")
        left_title.setStyleSheet("font-weight:bold")
        left_layout.addWidget(left_title)
        self.herb_table = QTableWidget(0, 5)
        self.herb_table.setHorizontalHeaderLabels(["ID", "饮片", "单价/g", "毒性", "备注"])
        self.herb_table.cellDoubleClicked.connect(self._add_tcm_herb)
        self.herb_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        left_layout.addWidget(self.herb_table, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 0, 0, 0)
        form_box = QGroupBox("开中药处方")
        form = QFormLayout(form_box)
        self.tcm_formula = QLineEdit()
        self.tcm_formula.setPlaceholderText("方名，如 银翘散")
        self.tcm_packs = QSpinBox()
        self.tcm_packs.setRange(1, 100)
        self.tcm_packs.setValue(1)
        self.tcm_decoct = QComboBox()
        self.tcm_decoct.addItem("代煎", "decoct")
        self.tcm_decoct.addItem("自煎", "self")
        self.tcm_usage = QComboBox()
        self.tcm_usage.addItem("内服", "internal")
        self.tcm_usage.addItem("外用", "external")
        self.tcm_method = QLineEdit("常规煎煮")
        self.tcm_note = QLineEdit()
        self.tcm_note.setPlaceholderText("备注")
        form.addRow("方名", self.tcm_formula)
        form.addRow("剂数", self.tcm_packs)
        form.addRow("煎法", self.tcm_decoct)
        form.addRow("用法", self.tcm_usage)
        form.addRow("煎煮方法", self.tcm_method)
        form.addRow("备注", self.tcm_note)
        right_layout.addWidget(form_box)

        selected_title = QLabel("本方饮片（剂量可改）")
        selected_title.setStyleSheet("font-weight:bold")
        right_layout.addWidget(selected_title)
        self.tcm_table = QTableWidget(0, 4)
        self.tcm_table.setHorizontalHeaderLabels(["ID", "饮片", "剂量g", "煎法"])
        self.tcm_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.tcm_table, 1)
        self.tcm_msg = QLabel("")
        self.tcm_msg.setWordWrap(True)
        right_layout.addWidget(self.tcm_msg)
        row = QHBoxLayout()
        remove = QPushButton("移除选中")
        remove.clicked.connect(self._remove_tcm_item)
        submit = QPushButton("开中药处方")
        submit.clicked.connect(self._create_tcm_prescription)
        row.addWidget(remove)
        row.addStretch(1)
        row.addWidget(submit)
        right_layout.addLayout(row)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([650, 520])
        layout.addWidget(splitter, 1)
        self.tcm_items: list[dict] = []
        return page

    def _on_rx_type_changed(self, _index: int) -> None:
        if not hasattr(self, "tcm_herb_rows"):
            self._load_tcm_herbs()

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
        form = self.rx_form_filter.currentData() if hasattr(self, "rx_form_filter") else ""
        if form:
            def matches(drug: dict) -> bool:
                text = f"{drug.get('name', '')}{drug.get('dosage_form', '')}"
                if form == "注射":
                    return "注射" in text
                if form == "口服":
                    return any(key in text for key in ("口服", "片", "胶囊", "颗粒", "丸", "糖浆"))
                if form == "外用":
                    return any(key in text for key in ("外用", "膏", "贴", "滴眼", "滴鼻", "栓"))
                return not any(key in text for key in ("注射", "口服", "片", "胶囊", "颗粒", "丸", "外用", "膏", "贴", "滴眼"))

            rows = [drug for drug in rows if matches(drug)]
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
        filters = " / ".join(
            part for part in (term, form) if part
        )
        self.rx_msg.setText(f"药品 {len(rows)} 种" + (f"（筛选：{filters}）" if filters else ""))

    def _load_tcm_herbs(self) -> None:
        try:
            self.tcm_herb_rows = self.api.list_tcm_herbs()
        except ApiError as e:
            self.tcm_msg.setText(f"饮片加载失败（{e.status_code}）：{e.detail}")
            return
        self._filter_tcm_herbs()

    def _filter_tcm_herbs(self) -> None:
        term = self.tcm_search.text().strip().lower() if hasattr(self, "tcm_search") else ""
        rows = getattr(self, "tcm_herb_rows", [])
        if term:
            rows = [row for row in rows if term in str(row.get("name", "")).lower()]
        self.tcm_herb_filtered = rows
        self.herb_table.setRowCount(len(rows))
        for index, herb in enumerate(rows):
            values = [
                str(herb["id"]),
                herb["name"],
                f"{herb.get('price_per_g', 0):.2f}",
                {"none": "普通", "toxic": "毒性", "precious": "贵重"}.get(
                    herb.get("toxicity"), herb.get("toxicity") or ""
                ),
                herb.get("note") or "",
            ]
            for col, value in enumerate(values):
                self.herb_table.setItem(index, col, QTableWidgetItem(str(value)))
        self.tcm_msg.setText(f"饮片 {len(rows)} 种" + (f"（筛选：{term}）" if term else ""))

    def _add_tcm_herb(self, row: int, _col: int) -> None:
        rows = getattr(self, "tcm_herb_filtered", [])
        if not (0 <= row < len(rows)):
            return
        herb = rows[row]
        if any(item["herb_id"] == herb["id"] for item in self.tcm_items):
            self.tcm_msg.setText(f"{herb['name']} 已在方中")
            return
        self.tcm_items.append(
            {
                "herb_id": herb["id"],
                "herb_name": herb["name"],
                "dose_g": 10.0,
                "special": "none",
            }
        )
        self._render_tcm_items()

    def _remove_tcm_item(self) -> None:
        row = self.tcm_table.currentRow()
        if 0 <= row < len(self.tcm_items):
            self.tcm_items.pop(row)
            self._render_tcm_items()

    def _render_tcm_items(self) -> None:
        labels = [
            ("常规", "none"),
            ("先煎", "first"),
            ("后下", "last"),
            ("包煎", "wrap"),
            ("另煎", "separate"),
            ("烊化", "melt"),
            ("冲服", "infuse"),
        ]
        self.tcm_table.setRowCount(len(self.tcm_items))
        for row, item in enumerate(self.tcm_items):
            self.tcm_table.setItem(row, 0, QTableWidgetItem(str(item["herb_id"])))
            self.tcm_table.setItem(row, 1, QTableWidgetItem(item["herb_name"]))
            self.tcm_table.setItem(row, 2, QTableWidgetItem(f"{item['dose_g']:.1f}"))
            combo = QComboBox()
            for text, value in labels:
                combo.addItem(text, value)
            index = combo.findData(item.get("special") or "none")
            if index >= 0:
                combo.setCurrentIndex(index)
            self.tcm_table.setCellWidget(row, 3, combo)
        self.tcm_msg.setText(f"本方 {len(self.tcm_items)} 味饮片")

    def _create_tcm_prescription(self) -> None:
        encounter_id = self.rx_encounter_id.value()
        if not encounter_id:
            self.tcm_msg.setText("请先选择已接诊患者")
            return
        if not self.tcm_items:
            self.tcm_msg.setText("请先双击左侧饮片加入处方")
            return
        items = []
        for row, item in enumerate(self.tcm_items):
            dose_item = self.tcm_table.item(row, 2)
            try:
                dose = float((dose_item.text() if dose_item else "").strip())
            except ValueError:
                self.tcm_msg.setText(f"{item['herb_name']} 剂量无效")
                return
            if dose <= 0:
                self.tcm_msg.setText(f"{item['herb_name']} 剂量必须大于 0")
                return
            combo = self.tcm_table.cellWidget(row, 3)
            items.append(
                {
                    "herb_id": item["herb_id"],
                    "dose_g": dose,
                    "special": combo.currentData() if combo else "none",
                    "note": "",
                }
            )
        payload = {
            "formula_name": self.tcm_formula.text().strip(),
            "usage": self.tcm_usage.currentData(),
            "packs": self.tcm_packs.value(),
            "decoct_service": self.tcm_decoct.currentData(),
            "decoction_method": self.tcm_method.text().strip() or "常规煎煮",
            "note": self.tcm_note.text().strip(),
            "items": items,
        }
        try:
            prescription = self.api.create_tcm_prescription(encounter_id, payload)
        except ApiError as e:
            self.tcm_msg.setText(f"开中药方失败（{e.status_code}）：{e.detail}")
            return
        self.tcm_items = []
        self._render_tcm_items()
        self.tcm_msg.setText(
            f"中药处方已开：{prescription['prescription_no']}，"
            f"金额 {prescription['total_amount']:.2f} 元"
        )

    def _pick_drug_row(self, row: int, _col: int) -> None:
        cell = self.drug_table.item(row, 0)
        if not cell:
            return
        self.rx_drug_id.setText(cell.text())
        if not self.rx_frequency.text().strip():
            self.rx_frequency.setText("bid")
        if not self.rx_route.text().strip():
            dosage = self.drug_table.item(row, 1).text() if self.drug_table.item(row, 1) else ""
            self.rx_route.setText("静滴" if "注射" in dosage else "口服")

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

        list_row = QHBoxLayout()
        list_row.addWidget(QLabel("本次已开检验 / 检查"))
        refresh_requests = QPushButton("刷新已开单")
        refresh_requests.clicked.connect(self._refresh_exam_requests)
        list_row.addStretch(1)
        list_row.addWidget(refresh_requests)
        layout.addLayout(list_row)
        self.exam_table = QTableWidget(0, 5)
        self.exam_table.setHorizontalHeaderLabels(["类型", "项目", "状态", "结果", "时间"])
        self.exam_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.exam_table, 1)
        return page

    def _refresh_exam_requests(self) -> None:
        if not hasattr(self, "exam_table"):
            return
        encounter_id = self.exam_encounter_id.value()
        if not encounter_id:
            self.exam_table.setRowCount(0)
            return
        rows = []
        try:
            for request in self.api.list_lab_requests(encounter_id):
                rows.append(
                    (
                        "检验",
                        request.get("item_name") or "",
                        request.get("status") or "",
                        request.get("result") or "",
                        str(request.get("created_at") or "")[:16].replace("T", " "),
                    )
                )
            for request in self.api.list_imaging_requests(encounter_id):
                rows.append(
                    (
                        "检查",
                        request.get("item_name") or "",
                        request.get("status") or "",
                        request.get("report") or request.get("result") or "",
                        str(request.get("created_at") or "")[:16].replace("T", " "),
                    )
                )
        except ApiError as e:
            self.exam_msg.setText(f"已开单加载失败：{e.detail}")
            return
        self.exam_table.setRowCount(len(rows))
        for index, values in enumerate(rows):
            for col, value in enumerate(values):
                self.exam_table.setItem(index, col, QTableWidgetItem(str(value)))
        self.exam_msg.setText(f"本次已开 {len(rows)} 项检验/检查")

    def _refresh_treatments(self) -> None:
        if not hasattr(self, "treat_table"):
            return
        encounter_id = self.treat_encounter_id.value()
        if not encounter_id:
            self.treat_table.setRowCount(0)
            return
        try:
            rows = self.api.list_treatments(encounter_id)
        except ApiError as e:
            self.treat_msg.setText(f"已开治疗加载失败：{e.detail}")
            return
        self.treat_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row.get("item_name") or "",
                str(row.get("quantity") or ""),
                {"pending": "待执行", "done": "已执行", "cancelled": "已取消"}.get(
                    row.get("status") or "", row.get("status") or ""
                ),
                row.get("executed_by") or "—",
            ]
            for col, value in enumerate(values):
                self.treat_table.setItem(index, col, QTableWidgetItem(str(value)))
        self.treat_msg.setText(f"本次已开 {len(rows)} 条治疗")

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
        self._refresh_exam_requests()

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
        self._refresh_exam_requests()

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

        list_row = QHBoxLayout()
        list_row.addWidget(QLabel("本次已开治疗"))
        refresh_list = QPushButton("刷新已开治疗")
        refresh_list.clicked.connect(self._refresh_treatments)
        list_row.addStretch(1)
        list_row.addWidget(refresh_list)
        layout.addLayout(list_row)
        self.treat_table = QTableWidget(0, 4)
        self.treat_table.setHorizontalHeaderLabels(["项目", "数量", "状态", "执行人"])
        self.treat_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.treat_table, 1)
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
        self._refresh_treatments()

