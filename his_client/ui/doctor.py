"""门诊工作站：叫号接诊、结构化病历、开方（含用法）、检验检查开单、治疗开单。"""
from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from datetime import date, datetime
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QSizePolicy,
    QGroupBox,
    QHBoxLayout,
    QDialog,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QScrollArea,
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
from his_client.ui.theme import apply_theme, colors, register_theme_listener
from his_client.config import load_config
from his_client.labels import zh
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.patient_banner import PatientBanner
from his_client.ui.birth_age import BirthAgeEditor, parse_id_birth
from his_client.ui.catalog_proposal import CatalogProposalDialog
from his_client.ui.prescription_dialog import PrescriptionQuickDialog
from his_client.ui.print_preview import open_print_preview
from his_client.ui.prescription_edit import PrescriptionEditDialog
from his_client.ui.table_policy import set_column_layout

try:
    from pypinyin import Style, lazy_pinyin
except ImportError:  # 未安装拼音依赖时退化为药名/规格搜索
    Style = None
    lazy_pinyin = None
from his_client.ui.adverse_reaction_dialog import AdverseReactionDialog
from his_client.ui.patient_info_panel import PatientInfoPanel
from his_client.ui.patient_clinical_dialog import PatientClinicalDialog
from his_client.ui.diagnosis_editor import DiagnosisDialog, DiagnosisEditor
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


RX_STATUS_LABELS = {
    "pending_review": "待审方",
    "approved": "已审方",
    "rejected": "已退回",
    "dispensing": "调配中",
    "dispensed": "已发药",
    "returned": "已退药",
    "cancelled": "已作废",
}
TCM_STATUS_LABELS = {
    "pending": "待审核",
    "reviewed": "已审核",
    "dispensed": "已发药",
    "decocting": "煎药中",
    "completed": "已完成",
    "cancelled": "已取消",
}
TREATMENT_STATUS_LABELS = {
    "pending": "待执行",
    "done": "已执行",
    "cancelled": "已取消",
}


class DoctorWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.config = load_config()
        self.insurance_enabled = self.config.insurance_enabled
        self.banner = PatientBanner()
        self.tabs = SidebarTabs()
        self.tabs.addTab(self._build_workbench_tab(), "门诊队列")
        self.tabs.addTab(self._build_reception_tab(), "接诊登记")
        self.tabs.addTab(self._build_register_tab(), "挂号")
        self.tabs.addTab(self._build_record_tab(), "病历")
        self.tabs.addTab(self._build_history_tab(), "历史诊疗")
        self.tabs.addTab(self._build_prescription_tab(), "开方")
        self.tabs.addTab(self._build_exam_tab(), "检验 / 检查")
        self.tabs.addTab(self._build_treatment_tab(), "治疗")
        self.payment_panel = PaymentPanel(api, compact=True)
        self.payment_panel.payment_completed.connect(self._on_payment_completed)
        self.tabs.addTab(self.payment_panel, "收费")
        self.tabs.setTabToolTip(0, "门诊队列：总览待接诊、接诊中、治疗中、挂起、已收费，双击开始接诊")
        self.tabs.setTabToolTip(1, "接诊登记：给已挂号患者创建就诊记录，也可开始接诊")
        self.tabs.setTabToolTip(4, "历史诊疗：无需挂号/接诊，只读查询患者历史")
        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        self.critical_badge = QPushButton("")
        self.critical_badge.setVisible(False)
        self.critical_badge.setCursor(Qt.PointingHandCursor)
        self._style_critical_badge()
        self.critical_badge.clicked.connect(self._focus_critical)
        layout.addWidget(self.critical_badge, 0, Qt.AlignLeft)
        body = QHBoxLayout()
        self.side_panel = QWidget()
        self.side_panel.setFixedWidth(300)
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(0, 0, 8, 0)
        self.side_info = PatientInfoPanel(editable=True)
        self.side_info.edit_requested.connect(self._edit_patient_clinical)
        # 工作台不再重复放一张患者卡；统一使用左侧患者摘要
        self.patient_info = self.side_info
        self.patient_info.edit_requested.connect(self._edit_patient_clinical)
        side_layout.addWidget(self.side_info)
        history_row = QHBoxLayout()
        history_title = QLabel("历史就诊")
        history_title.setStyleSheet("font-weight:bold;margin-top:6px")
        history_row.addWidget(history_title)
        history_row.addStretch(1)
        side_layout.addLayout(history_row)
        self.side_history = QTableWidget(0, 6)
        self.side_history.setHorizontalHeaderLabels(
            ["日期", "诊断", "医生", "处方", "检验", "治疗"]
        )
        self.side_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.side_history.verticalHeader().setVisible(False)
        self.side_history.cellDoubleClicked.connect(self._open_side_history)
        self.side_history.setContextMenuPolicy(Qt.CustomContextMenu)
        self.side_history.customContextMenuRequested.connect(self._side_history_menu)
        side_layout.addWidget(self.side_history, 1)
        self.side_history_msg = QLabel("默认不加载历史；在历史列表上右键选择“加载历史诊疗”")
        self.side_history_msg.setWordWrap(True)
        self.side_history_msg.setStyleSheet("color:#64748b")
        side_layout.addWidget(self.side_history_msg)
        body.addWidget(self.side_panel)
        body.addWidget(self.tabs, 1)
        layout.addLayout(body)
        self._load_diagnoses()
        self._load_registration_doctors()
        self._load_workbench()
        self._load_pending_registrations()
        self._install_shortcuts()
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_refresh)
        self.auto_timer.start(15000)
        self.side_panel.setFixedWidth(300)
        self.side_panel.setVisible(True)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._set_patient_actions(False)
        self._set_clinical_tabs(False, False)
        register_theme_listener(self)

    def _style_critical_badge(self) -> None:
        c = colors()
        self.critical_badge.setStyleSheet(
            f"QPushButton{{background:{c['card']};color:{c['danger']};"
            f"border:1px solid {c['danger']};border-radius:4px;padding:5px 10px;"
            "font-weight:bold;text-align:left;}"
            f"QPushButton:hover{{background:{c['selected']};}}"
        )

    def apply_theme(self) -> None:
        self._style_critical_badge()
        if hasattr(self, "wb_fee_summary"):
            self.wb_fee_summary.setStyleSheet(f"color:{colors()['muted']};")
        self.update()

    def _on_tab_changed(self, _index: int) -> None:
        # 侧栏始终保留固定宽度，避免切页时内容整体左右跳动
        label = self.tabs.tabText(self.tabs.currentIndex())
        if "开方" in label:
            if not hasattr(self, "drug_rows"):
                self._load_drugs()
            if self.banner.encounter_id:
                self._refresh_prescriptions()
        elif "病历" in label and self.banner.encounter_id:
            self._load_record()
        elif "检验" in label:
            if self.banner.encounter_id:
                self._load_lab_items()
                self._load_imaging_items()
                self._refresh_exam_requests()
        elif "收费" in label:
            self._sync_payment_panel(self.banner.encounter_id)

    def _print_current(self) -> None:
        encounter_id = self.banner.encounter_id
        if not encounter_id:
            self.wb_summary.setText("请先选择患者并接诊")
            return
        open_print_preview(
            self, self.api.prescription_print_url(encounter_id), "处方打印预览"
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
        current = getattr(self, "wb_current", None)
        if current and current.get("encounter_id"):
            try:
                encounter = self.api.get_encounter(current["encounter_id"])
            except ApiError:
                encounter = None
            if encounter and encounter.get("status") == "closed":
                self._on_payment_completed()
                return
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
        for label in ("全部", "待接诊", "接诊中", "治疗中", "已挂起", "已收费"):
            self.wb_status_tabs.addTab(label)
        self.wb_status_tabs.currentChanged.connect(self._filter_workbench)
        queue_layout.addWidget(self.wb_status_tabs)
        queue_hint = QLabel("总览：待接诊 / 接诊中 / 治疗中 / 挂起 / 已收费；双击行开始接诊")
        queue_hint.setStyleSheet("color:#64748b;")
        queue_layout.addWidget(queue_hint)
        self.wb_empty = QLabel("暂无匹配患者\n调整搜索条件或点击刷新")
        self.wb_empty.setAlignment(Qt.AlignCenter)
        self.wb_empty.setStyleSheet("color:#64748b;padding:24px;font-size:14px")
        self.wb_empty.setVisible(False)
        queue_layout.addWidget(self.wb_empty)

        self.wb_table = QTableWidget(0, 7)
        self.wb_table.setHorizontalHeaderLabels(
            ["挂号", "患者", "类型", "挂号状态", "就诊", "诊断", "待缴"]
        )
        # 医生看自己的队列，医生列不重复占用宽度；患者/诊断优先
        set_column_layout(self.wb_table, stretch=(1, 5), contents=(0, 2, 3, 4, 6))
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
        self.wb_patient = QLabel("请选择患者")
        self.wb_patient.setWordWrap(True)
        self.wb_patient.setVisible(False)

        self.critical_box = QGroupBox("危急值待确认")
        self.critical_box.setMinimumHeight(170)
        critical_layout = QVBoxLayout(self.critical_box)
        self.critical_table = QTableWidget(0, 5)
        self.critical_table.setHorizontalHeaderLabels(
            ["患者", "项目", "结果", "报告时间", "超时"]
        )
        self.critical_table.setMinimumHeight(110)
        self.critical_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.critical_table.cellClicked.connect(self._select_critical)
        critical_layout.addWidget(self.critical_table, 1)
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
        # 当前患者操作区。诊断不在接诊前录入，统一在「病历」页完成。
        self.wb_context = QWidget()
        context_layout = QVBoxLayout(self.wb_context)
        context_layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.wb_start = QPushButton("开始接诊")
        self.wb_start.clicked.connect(self._start_workbench)
        self.wb_convert = QPushButton("复诊转初诊")
        self.wb_convert.setVisible(False)
        self.wb_convert.clicked.connect(self._convert_followup_to_initial)
        row.addWidget(self.wb_start)
        row.addWidget(self.wb_convert)
        row.addStretch(1)
        context_layout.addLayout(row)

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
                ("回诊 / 看结果", self._return_workbench),
            ]
        ):
            button = QPushButton(text)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(handler)
            self.wb_action_buttons[text] = button
            actions.addWidget(button, index // 3, index % 3)
        context_layout.addLayout(actions)

        self.wb_summary = QLabel("")
        self.wb_summary.setWordWrap(True)
        context_layout.addWidget(self.wb_summary)
        self.wb_fee_summary = QLabel("")
        self.wb_fee_summary.setWordWrap(True)
        self.wb_fee_summary.setStyleSheet("color:#64748b;")
        context_layout.addWidget(self.wb_fee_summary)
        self.wb_followup_hint = QLabel("")
        self.wb_followup_hint.setWordWrap(True)
        self.wb_followup_hint.setStyleSheet("color:#b45309;font-weight:bold")
        self.wb_followup_hint.setVisible(False)
        context_layout.addWidget(self.wb_followup_hint)
        context_layout.addStretch(1)

        # 危急值跨患者，固定在工作台右下角，与当前患者操作区分割，高度可调并记忆。
        self.critical_splitter = QSplitter(Qt.Vertical)
        self.critical_splitter.addWidget(self.wb_context)
        self.critical_splitter.addWidget(self.critical_box)
        self.critical_splitter.setChildrenCollapsible(False)
        self.critical_splitter.setStretchFactor(0, 3)
        self.critical_splitter.setStretchFactor(1, 1)
        self.critical_splitter.splitterMoved.connect(self._save_critical_split)
        right_layout.addWidget(self.critical_splitter, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([800, 520])
        layout.addWidget(splitter, 1)
        self._restore_critical_split()
        return page

    def _load_diagnoses(self) -> None:
        try:
            rows = self.api.list_diagnoses()
        except ApiError:
            return
        self.diagnoses = rows
        if hasattr(self, "record_diagnosis_editor"):
            self.record_diagnosis_editor.set_options(rows)

    def _edit_patient_clinical(self) -> None:
        current = getattr(self, "wb_current", None)
        patient_id = current.get("patient_id") if current else None
        if not patient_id:
            patient_id = getattr(self, "side_info", None).patient_id
        if not patient_id:
            self.wb_summary.setText("请先选择患者")
            return
        try:
            patient = self.api.get_patient(patient_id)
        except ApiError as e:
            self.wb_summary.setText(f"加载患者失败（{e.status_code}）：{e.detail}")
            return
        dialog = PatientClinicalDialog(patient, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            updated = self.api.update_patient_clinical(patient_id, dialog.payload())
        except ApiError as e:
            QMessageBox.warning(self, "保存失败", f"{e.status_code}：{e.detail}")
            return
        registration_id = current.get("registration_id") if current else None
        self._load_workbench()
        if registration_id:
            for index, row in enumerate(getattr(self, "workbench_rows", [])):
                if row.get("registration_id") == registration_id:
                    self.wb_table.selectRow(index)
                    self._select_workbench(index, 0)
                    break
        self.wb_summary.setText(
            f"患者史已更新并留痕：{updated.get('allergy_label') or '过敏不详'}"
        )

    def _set_rx_enabled(self, enabled: bool) -> None:
        for name in ("rx_table", "rx_edit", "rx_delete", "tcm_inj_table", "tcm_inj_rx_table"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(enabled)

    def _set_clinical_tabs(
        self, has_patient: bool, has_encounter: bool, closed: bool = False
    ) -> None:
        clinical_enabled = has_encounter and not closed
        allowed = {
            "病历": clinical_enabled,
            # 历史诊疗是独立只读查询：不需要挂号/接诊，始终可用
            "历史诊疗": True,
            "开方": clinical_enabled,
            "收费": clinical_enabled,
            "检验 / 检查": clinical_enabled,
            "治疗": clinical_enabled,
        }
        for text, enabled in allowed.items():
            for index in range(self.tabs.count()):
                if self.tabs.tabText(index) == text:
                    self.tabs.setTabEnabled(index, enabled)
                    break
        current = self.tabs.currentIndex()
        if current >= 0 and not self.tabs.isTabEnabled(current):
            self.tabs.setCurrentIndex(0)

    def _on_payment_completed(self) -> None:
        """收费即完诊：回队列，清空当前患者，等待选择下一位。"""
        self.wb_current = None
        self._active_patient_id = None
        self._active_patient_name = ""
        self._clear_side_history()
        self.wb_table.clearSelection()
        self.banner.clear()
        self.side_info.clear()
        self._set_patient_actions(False)
        self._set_clinical_tabs(False, False)
        self._load_workbench()
        self.tabs.setCurrentIndex(0)
        self.wb_summary.setText("收费完成，请选择下一位患者")

    def _set_patient_actions(self, enabled: bool) -> None:
        """没有选中患者时，右侧所有临床动作不可用。"""
        self._set_rx_enabled(enabled)
        for name in ("wb_start", "wb_convert"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(enabled)
        for button in getattr(self, "wb_action_buttons", {}).values():
            button.setEnabled(enabled)

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
            3: "treatment",
            4: "paused",
            5: "closed",
        }.get(index, "")
        if status_filter == "waiting":
            rows = [item for item in all_rows if not item.get("encounter_id")]
        elif status_filter == "treatment":
            rows = [item for item in all_rows if item.get("treatment_status") == "in_progress"]
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
        self.wb_empty.setVisible(not rows)
        self.wb_table.setVisible(bool(rows))
        self.wb_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            gender = {"male": "男", "female": "女"}.get(
                item.get("gender"), "性别不详"
            )
            age = item.get("age")
            allergy = item.get("allergy_label") or "过敏史不详"
            allergy_present = item.get("allergy_status") == "present"
            level = item.get("triage_level")
            level_text = f"[{level}级]" if level else ""
            compact_patient = f"{level_text}{item['patient_name']}"
            compact_patient += f" {age}岁" if age is not None else " 年龄不详"
            if allergy_present:
                compact_patient += " ⚠过敏"
            full_patient = (
                f"{item['patient_name']} {gender}/"
                f"{age if age is not None else '年龄不详'} 过敏：{allergy}"
            )
            values = [
                str(item["registration_id"]),
                compact_patient,
                "复诊" if item.get("visit_type") == "follow_up" else "初诊",
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
                cell = QTableWidgetItem(str(value))
                if col == 1:
                    cell.setToolTip(full_patient)
                if col == 4 and item.get("encounter_date"):
                    cell.setToolTip(
                        f"就诊日期：{item['encounter_date']}；"
                        f"状态：{item.get('encounter_status') or '—'}"
                    )
                self.wb_table.setItem(row, col, cell)
        total = len(getattr(self, "workbench_all", rows))
        cross_count = sum(1 for item in all_rows if item.get("cross_day"))
        suffix = f"（含跨日未完成 {cross_count}）" if cross_count else ""
        self.wb_summary.setText(
            f"显示 {len(rows)} / 队列 {total} 人{suffix}"
            if term or status_filter
            else f"队列 {total} 人{suffix}"
        )
        waiting = sum(1 for item in all_rows if not item.get("encounter_id"))
        open_count = sum(1 for item in all_rows if item.get("encounter_status") == "open")
        paused_count = sum(1 for item in all_rows if item.get("encounter_status") == "paused")
        treatment_count = sum(
            1 for item in all_rows if item.get("treatment_status") == "in_progress"
        )
        closed_count = sum(1 for item in all_rows if item.get("encounter_status") == "closed")
        if hasattr(self, "wb_status_tabs"):
            for index, (label, count) in enumerate(
                zip(
                    ("全部", "待接诊", "接诊中", "治疗中", "已挂起", "已收费"),
                    (total, waiting, open_count, treatment_count, paused_count, closed_count),
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

    def _critical_settings(self):
        path = str(getattr(self.config, "ui_state_path", "") or "")
        if not path:
            return None
        return QSettings(path, QSettings.IniFormat)

    def _restore_critical_split(self) -> None:
        settings = self._critical_settings()
        if settings is None:
            self.critical_splitter.setSizes([320, 260])
            return
        value = settings.value("workbench/critical_split_v3", [320, 260])
        try:
            sizes = [int(x) for x in list(value)]
        except (TypeError, ValueError):
            sizes = [320, 260]
        if len(sizes) != 2 or min(sizes) < 60:
            sizes = [320, 260]
        self.critical_splitter.setSizes(sizes)

    def _save_critical_split(self, *_args) -> None:
        settings = self._critical_settings()
        if settings is not None:
            settings.setValue("workbench/critical_split_v3", self.critical_splitter.sizes())
            settings.sync()

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
            overdue = sum(1 for x in alerts if x.get("critical_overdue"))
            self.critical_msg.setText(f"待确认 {len(alerts)} 条；超时 {overdue} 条")
            self.critical_msg.setStyleSheet("color:#ef4444;font-weight:bold")
            if hasattr(self, "critical_badge"):
                self.critical_badge.setText(
                    f"! 危急值待确认 {len(alerts)} 条"
                    + (f"（超时 {overdue}）" if overdue else "")
                )
                self.critical_badge.setVisible(True)
        else:
            self.critical_msg.setText("暂无未确认危急值")
            self.critical_msg.setStyleSheet("")
            if hasattr(self, "critical_badge"):
                self.critical_badge.setVisible(False)

    def _focus_critical(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.critical_table.setFocus()

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

    @staticmethod
    def _workbench_status_text(item: dict) -> str:
        treatment = item.get("treatment_status")
        if treatment == "in_progress":
            return "治疗中"
        if treatment == "waiting":
            return "待治疗"
        return {
            "open": "进行中",
            "paused": "已挂起",
            "closed": "已收费",
        }.get(item.get("encounter_status"), item.get("encounter_status") or "")

    @staticmethod
    def _is_active_patient(item: dict) -> bool:
        """只有接诊中/挂起/治疗中的患者才进入全局患者条和左侧患者卡。"""
        return (
            item.get("encounter_status") in ("open", "paused")
            or item.get("treatment_status") in ("waiting", "in_progress")
        )

    def _select_workbench(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self.workbench_rows)):
            return
        item = self.workbench_rows[row]
        active = self._is_active_patient(item)
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
        if item.get("treatment_status") == "in_progress":
            status = "治疗中"
        elif item.get("treatment_status") == "waiting":
            status = "待治疗"
        elif status_text := item.get("encounter_status"):
            status = {"open": "接诊中", "paused": "已挂起", "closed": "已收费"}.get(
                status_text, "已接诊" if item.get("encounter_id") else "待接诊"
            )
        else:
            status = "已接诊" if item.get("encounter_id") else "待接诊"
        # 有正在接诊的患者时，单击队列里的其他患者只切换顶部查看，
        # 不切换当前接诊上下文、不改变病历/开方/检验/治疗页签。
        active_id = getattr(self, "_active_patient_id", None)
        if active_id and item.get("patient_id") != active_id and not active:
            self.banner.set_patient(patient, item.get("encounter_id"), status)
            active_name = getattr(self, "_active_patient_name", "") or f"患者 {active_id}"
            self.wb_summary.setText(
                f"当前接诊患者仍是 {active_name}；刚才点击的 {item.get('patient_name') or ''} 仅用于查看"
            )
            return
        self.wb_current = item
        self._set_patient_actions(True)
        # 顶部始终显示队列中刚刚点击的患者；左侧只显示当前真正接诊中的患者。
        self.banner.set_patient(patient, item.get("encounter_id"), status)
        if active:
            self._active_patient_id = item.get("patient_id")
            self._active_patient_name = item.get("patient_name") or ""
            self.side_info.set_patient(
                patient,
                item.get("encounter_id"),
                status,
                f"分诊：{item.get('triage_level') or '—'} 级\n"
                f"生命体征：{item.get('vital_summary') or '未测'}",
            )
            self._clear_side_history()
        elif not getattr(self, "_active_patient_id", None):
            self.side_info.clear()
            self._clear_side_history()
        gender = {"male": "男", "female": "女"}.get(
            item.get("gender"), "性别不详"
        )
        age = item.get("age")
        allergy = item.get("allergy_label") or "过敏史不详"
        self.wb_patient.setText(
            f"{item['patient_name']} · {gender}/"
            f"{age if age is not None else '年龄不详'} · "
            f"{'复诊' if item.get('visit_type') == 'follow_up' else '初诊'} · "
            f"过敏：{allergy} · 分诊 {item.get('triage_level') or '—'} 级 · "
            f"{item.get('vital_summary') or '未测生命体征'} · "
            f"挂号 {item['registration_id']} · 就诊 {item.get('encounter_id') or '未接诊'}"
            + (" · 跨日未完成" if item.get("cross_day") else "")
        )
        if item.get("isolation"):
            self.wb_patient.setText(self.wb_patient.text() + " · 隔离提示")
            self.wb_patient.setStyleSheet("color:#ef4444;font-weight:bold")
        elif item.get("allergy_label") not in (None, "", "无过敏史", "过敏史不详"):
            self.wb_patient.setStyleSheet("color:#ef4444;font-weight:bold")
        else:
            self.wb_patient.setStyleSheet("")
        follow_up = item.get("visit_type") == "follow_up"
        self.wb_followup_hint.setVisible(follow_up)
        if follow_up:
            self.wb_followup_hint.setText(
                "复诊流程：先看历史诊疗 → 核对上次诊断/医嘱 → 本次记录复诊；"
                "不需要重新开药时可直接写复诊记录；病情变化点「复诊转初诊」"
            )
        self.wb_convert.setVisible(follow_up and not item.get("encounter_id"))
        status = item.get("encounter_status") or ""
        self.wb_start.setEnabled(not item.get("encounter_id") or status == "paused")
        if hasattr(self, "wb_action_buttons"):
            has_encounter = bool(item.get("encounter_id"))
            self._set_clinical_tabs(True, has_encounter, status == "closed")
            self._set_rx_enabled(has_encounter and status != "closed")
            for text in ("写病历", "开方", "开检验", "开治疗", "历史诊疗"):
                self.wb_action_buttons[text].setEnabled(has_encounter)
            self.wb_action_buttons["挂起当前"].setEnabled(status == "open")
            self.wb_action_buttons["继续接诊"].setEnabled(status == "paused")
            self.wb_action_buttons["药物反应 / 换药"].setEnabled(has_encounter)
            self.wb_action_buttons["回诊 / 看结果"].setEnabled(
                has_encounter and status == "closed"
            )
            if has_encounter and status == "closed":
                for text in ("写病历", "开方", "开检验", "开治疗", "挂起当前", "继续接诊", "药物反应 / 换药"):
                    self.wb_action_buttons[text].setEnabled(False)
        if item.get("encounter_id"):
            self._set_encounter_everywhere(item["encounter_id"])
            self._load_workbench_summary(item["encounter_id"])
        else:
            self._set_encounter_everywhere(None)
            self.wb_fee_summary.setText("")
            self.wb_summary.setText("尚未接诊，点「开始接诊」；诊断在病历页填写")

    def _load_workbench_summary(self, encounter_id: int) -> None:
        try:
            summary = self.api.encounter_summary(encounter_id)
        except ApiError as e:
            self.wb_summary.setText(f"加载就诊摘要失败（{e.status_code}）：{e.detail}")
            return
        self.wb_summary_data = summary
        self.wb_summary.setText(
            f"{'复诊' if summary.get('visit_type') == 'follow_up' else '初诊'}　"
            f"诊断：{summary.get('diagnosis_code') or ''} {summary['diagnosis'] or '—'}　状态："
            f"{zh('encounter_status', summary['status'])}　"
            f"病历：{'已签名' if summary['record_signed'] else '未签名'}　"
            f"费用：{summary['total_amount']:.2f} 元（待缴 {summary['pending_amount']:.2f}）　"
            f"处方 {summary['prescription_count']} / 检验 {summary['lab_count']} / 治疗 {summary['treatment_count']}"
        )
        charges = summary.get("charges") or []
        pending = [x for x in charges if x.get("status") == "pending"]
        self.wb_fee_summary.setText(
            f"本次费用 {len(charges)} 项，待缴 {len(pending)} 项 ¥{summary['pending_amount']:.2f}；"
            "明细在「收费」页"
        )
        self.reg_id.setValue(summary["registration_id"])
        self.mr_encounter_id.setValue(encounter_id)
        self.rx_encounter_id.setValue(encounter_id)
        self.exam_encounter_id.setValue(encounter_id)
        self.treat_encounter_id.setValue(encounter_id)

    def _convert_followup_to_initial(self) -> None:
        item = getattr(self, "wb_current", None)
        if not item:
            self.wb_summary.setText("请先选择患者")
            return
        if item.get("encounter_id"):
            self.wb_summary.setText("已接诊，不能修改挂号类型")
            return
        try:
            self.api.update_registration_visit_type(item["registration_id"], "initial")
        except ApiError as e:
            self.wb_summary.setText(f"转初诊失败（{e.status_code}）：{e.detail}")
            return
        registration_id = item["registration_id"]
        self._load_workbench()
        for row, candidate in enumerate(getattr(self, "workbench_rows", [])):
            if candidate.get("registration_id") == registration_id:
                self.wb_table.selectRow(row)
                self._select_workbench(row, 0)
                break
        self.wb_summary.setText("已转为初诊；接诊时按初诊收挂号费")

    def _start_workbench(self) -> None:
        item = getattr(self, "wb_current", None)
        if not item:
            self.wb_summary.setText("请先选择患者")
            return
        try:
            if item.get("encounter_status") == "paused" and item.get("encounter_id"):
                encounter = self.api.resume_encounter(item["encounter_id"])
            else:
                encounter = self.api.create_encounter(item["registration_id"])
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
        diagnosis = encounter.get("diagnosis") or "待病历填写"
        self.patient_info.set_patient(
            patient, encounter["id"], "已接诊", f"诊断：{diagnosis}"
        )
        self._active_patient_id = item.get("patient_id")
        self._active_patient_name = item.get("patient_name") or ""
        self._clear_side_history()
        # 接诊成功直接进入病历，避免停在队列页以为没反应
        self._wb_record()

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

    def _return_workbench(self) -> None:
        """已收费患者回诊：同挂号新建回诊就诊，不重新挂号。"""
        item = getattr(self, "wb_current", None)
        if not item or not item.get("encounter_id"):
            self.wb_summary.setText("请先选择已收费患者")
            return
        if item.get("encounter_status") != "closed":
            self.wb_summary.setText("只有已收费关闭的就诊可以回诊")
            return
        try:
            encounter = self.api.return_encounter(item["encounter_id"])
        except ApiError as e:
            self.wb_summary.setText(f"回诊失败（{e.status_code}）：{e.detail}")
            return
        self._load_workbench()
        for row, candidate in enumerate(self.workbench_rows):
            if candidate["registration_id"] == item["registration_id"]:
                self.wb_table.selectRow(row)
                self._select_workbench(row, 0)
                break
        self.wb_summary.setText(
            f"已回诊：新就诊 {encounter['id']}（关联原就诊 {item['encounter_id']}），无需重新挂号"
        )
        self._wb_record()

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
                if self.tabs.isTabEnabled(index):
                    self.tabs.setCurrentIndex(index)
                return

    def _clear_side_history(self) -> None:
        self.side_history_data = []
        self.side_history.setRowCount(0)
        self._side_history_patient_id = None
        self.side_history_msg.setText(
            "默认不加载历史；在历史列表上右键选择“加载历史诊疗”"
        )

    def _side_history_menu(self, pos) -> None:
        patient_id = (
            (getattr(self, "side_info", None).patient_id if hasattr(self, "side_info") else 0)
            or (self.wb_current or {}).get("patient_id")
        )
        menu = QMenu(self)
        load = menu.addAction("加载历史诊疗（含处方/检验/治疗）")
        open_tab = menu.addAction("打开历史诊疗页")
        clear = menu.addAction("清空历史列表")
        load.setEnabled(bool(patient_id))
        open_tab.setEnabled(bool(patient_id))
        action = menu.exec(self.side_history.viewport().mapToGlobal(pos))
        if action == load and patient_id:
            self._load_side_history(patient_id, force=True)
        elif action == open_tab and patient_id:
            self._wb_history()
        elif action == clear:
            self._clear_side_history()

    def _load_side_history(self, patient_id: int | None, force: bool = False) -> None:
        if not patient_id:
            self._clear_side_history()
            return
        if not force and getattr(self, "_side_history_patient_id", None) == patient_id:
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
                str(len(encounter.get("prescriptions") or [])),
                str(len(encounter.get("lab_requests") or [])),
                str(len(encounter.get("treatments") or [])),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.side_history.setItem(row, col, item)
        self.side_history_msg.setText(
            f"共 {len(encounters)} 次；双击一行查看完整历史（处方/检验/治疗）"
            if encounters
            else "该患者没有历史就诊"
        )

    def _refresh_side_history(self) -> None:
        patient_id = getattr(self, "side_info", None).patient_id
        if patient_id:
            self._load_side_history(patient_id, force=True)

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
            label = getattr(self, f"{attr.replace('_id', '_label')}", None)
            if label is not None:
                label.setText(str(encounter_id) if encounter_id else "未接诊")
        if encounter_id:
            if hasattr(self, "rx_encounter_id"):
                self._refresh_prescriptions()
            if hasattr(self, "exam_table"):
                self._refresh_exam_requests()
            if hasattr(self, "treat_table"):
                self._refresh_treatments()
            if hasattr(self, "payment_panel"):
                self._sync_payment_panel(encounter_id)
        elif hasattr(self, "rx_table"):
            self.rx_table.setRowCount(0)
        if not hasattr(self, "side_info"):
            return
        if not encounter_id:
            return
        try:
            summary = self.api.encounter_summary(encounter_id)
        except ApiError:
            return
        if self._is_active_patient(getattr(self, "wb_current", {}) or {}):
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

    def _sync_payment_panel(self, encounter_id: int | None) -> None:
        panel = getattr(self, "payment_panel", None)
        if panel is None:
            return
        if not encounter_id:
            panel.encounter_id.setValue(0)
            panel.charge_table.setRowCount(0)
            panel.charge_empty.setVisible(True)
            return
        panel.encounter_id.setValue(int(encounter_id))
        current = getattr(self, "wb_current", None) or {}
        patient = {
            "id": current.get("patient_id"),
            "patient_no": current.get("patient_no"),
            "name": current.get("patient_name"),
            "gender": current.get("gender"),
            "age": current.get("age"),
            "phone": current.get("phone"),
        }
        if patient.get("id"):
            panel.patient_picker.set_patient(patient)
        try:
            panel._load_charges()
        except Exception:
            pass

    def _wb_record(self) -> None:
        if not self.wb_current or not self.wb_current.get("encounter_id"):
            self.wb_summary.setText("请先开始接诊，再打开病历")
            return
        self._switch_tab("病历")
        if hasattr(self, "mr_encounter_id"):
            self._set_encounter_everywhere(self.wb_current.get("encounter_id"))
            self._load_record()

    def _wb_prescribe(self) -> None:
        if not self.wb_current or not self.wb_current.get("encounter_id"):
            self.wb_summary.setText("请先开始接诊，再开方")
            return
        self._switch_tab("开方")
        self._set_encounter_everywhere(self.wb_current.get("encounter_id"))
        self._load_drugs()
        self._refresh_prescriptions()

    def _wb_exam(self) -> None:
        if not self.wb_current or not self.wb_current.get("encounter_id"):
            self.wb_summary.setText("请先开始接诊，再开检验/检查")
            return
        self._switch_tab("检验")
        self._set_encounter_everywhere(self.wb_current.get("encounter_id"))
        self._load_lab_items()
        self._load_imaging_items()
        self._refresh_exam_requests()

    def _wb_treat(self) -> None:
        if not self.wb_current or not self.wb_current.get("encounter_id"):
            self.wb_summary.setText("请先开始接诊，再开治疗")
            return
        self._switch_tab("治疗")
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
        search_box = QGroupBox("查询患者（可用身份证检索，结果不显示证件号/电话）")
        search_layout = QVBoxLayout(search_box)
        row = QHBoxLayout()
        self.reg_patient_name = QLineEdit()
        self.reg_patient_name.setPlaceholderText("姓名（可空）")
        self.reg_patient_id_number = QLineEdit()
        self.reg_patient_id_number.setPlaceholderText("身份证号（仅检索，不显示）")
        search = QPushButton("查询患者")
        search.clicked.connect(self._search_registration_patients)
        row.addWidget(QLabel("姓名"))
        row.addWidget(self.reg_patient_name)
        row.addWidget(QLabel("身份证号"))
        row.addWidget(self.reg_patient_id_number)
        row.addWidget(search)
        search_layout.addLayout(row)
        self.reg_patient_table = QTableWidget(0, 3)
        self.reg_patient_table.setHorizontalHeaderLabels(["患者编号", "姓名", "性别/年龄"])
        self.reg_patient_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        search_layout.addWidget(self.reg_patient_table, 1)
        left_layout.addWidget(search_box, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        quick_box = QGroupBox("快速建档并挂号")
        quick_form = QFormLayout(quick_box)
        self.qr_name = QLineEdit()
        self.qr_name.setPlaceholderText("姓名，必填")
        self.qr_phone = QLineEdit()
        self.qr_phone.setPlaceholderText("手机号，必填")
        self.qr_gender = QComboBox()
        self.qr_gender.addItem("性别不详", "unknown")
        self.qr_gender.addItem("男", "male")
        self.qr_gender.addItem("女", "female")
        self.qr_birth_age = BirthAgeEditor()
        self.qr_id_number = QLineEdit()
        self.qr_id_number.setPlaceholderText("身份证号（可后补，填完自动带出出生日期）")
        self.qr_id_number.editingFinished.connect(self._quick_id_changed)
        self.qr_mode_only = QRadioButton("仅建档，暂不挂号")
        self.qr_mode_register = QRadioButton("建档后立即挂号")
        self.qr_mode_register.setChecked(True)
        self.qr_mode_group = QButtonGroup(self)
        self.qr_mode_group.addButton(self.qr_mode_only)
        self.qr_mode_group.addButton(self.qr_mode_register)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.qr_mode_only)
        mode_row.addWidget(self.qr_mode_register)
        quick_btn = QPushButton("快速建档")
        quick_btn.clicked.connect(self._quick_create_and_register)
        quick_form.addRow("姓名", self.qr_name)
        quick_form.addRow("手机号", self.qr_phone)
        quick_form.addRow("性别", self.qr_gender)
        quick_form.addRow("身份证", self.qr_id_number)
        quick_form.addRow("", self.qr_birth_age)
        quick_form.addRow("处理方式", mode_row)
        quick_form.addRow("", quick_btn)
        right_layout.addWidget(quick_box)

        box = QGroupBox("现场挂号")
        form = QFormLayout(box)
        self.reg_patient_id = QLineEdit()
        self.reg_patient_id.setReadOnly(True)
        self.reg_patient_id.setVisible(False)
        self.reg_patient_id.setPlaceholderText("在左侧选择患者")
        self.reg_selected_label = QLabel("未选择患者")
        self.reg_selected_label.setWordWrap(True)
        self.reg_doctor = QComboBox()
        self.reg_doctor.currentIndexChanged.connect(self._confirm_doctor_change)
        load_doctors = QPushButton("刷新医生")
        load_doctors.clicked.connect(self._load_registration_doctors)
        doctor_row = QHBoxLayout()
        doctor_row.addWidget(self.reg_doctor)
        doctor_row.addWidget(load_doctors)
        self.reg_msg = QLabel("")
        self.reg_msg.setWordWrap(True)
        submit = QPushButton("挂号")
        submit.clicked.connect(self._create_registration)
        form.addRow("已选患者", self.reg_selected_label)
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
        self.reg_search_patients = patients
        self.reg_patient_table.setRowCount(len(patients))
        for row, patient in enumerate(patients):
            gender = {"male": "男", "female": "女"}.get(
                patient.get("gender"), "性别不详"
            )
            age = patient.get("age")
            values = [
                patient.get("patient_no") or str(patient["id"]),
                patient["name"],
                f"{gender}/{age if age is not None else '年龄不详'}",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 0:
                    cell.setData(Qt.UserRole, patient["id"])
                self.reg_patient_table.setItem(row, col, cell)
        self.reg_msg.setText(f"共 {len(patients)} 位患者（点击选择）")

    def _select_registration_patient(self, row: int, _col: int) -> None:
        item = self.reg_patient_table.item(row, 0)
        if not item:
            return
        patient_id = item.data(Qt.UserRole)
        if patient_id is None:
            return
        patient = next(
            (p for p in getattr(self, "reg_search_patients", []) if p["id"] == patient_id),
            None,
        )
        self.reg_patient_id.setText(str(patient_id))
        if patient:
            gender = {"male": "男", "female": "女"}.get(
                patient.get("gender"), "性别不详"
            )
            age = patient.get("age")
            self.reg_selected_label.setText(
                f"{patient.get('patient_no') or patient_id} "
                f"{patient['name']} · {gender}/"
                f"{age if age is not None else '年龄不详'}"
            )

    def _load_registration_doctors(self) -> None:
        try:
            doctors = self.api.list_doctors()
        except ApiError as e:
            self.reg_msg.setText(f"加载医生失败（{e.status_code}）：{e.detail}")
            return
        self._loading_doctors = True
        self.reg_doctor.blockSignals(True)
        self.reg_doctor.clear()
        for doctor in doctors:
            self.reg_doctor.addItem(
                f"{doctor['name']}（科室 {doctor.get('department_id')}）", doctor["id"]
            )
        self._default_doctor_id = None
        self._default_doctor_name = ""
        try:
            me = self.api.me()
        except ApiError:
            me = {}
        doctor_id = me.get("doctor_id")
        if doctor_id:
            for index, doctor in enumerate(doctors):
                if doctor.get("id") == doctor_id:
                    self.reg_doctor.setCurrentIndex(index)
                    self._default_doctor_id = doctor["id"]
                    self._default_doctor_name = str(doctor.get("name") or "")
                    break
        if self._default_doctor_id is None and me.get("role") == "doctor":
            display = str(me.get("display_name") or me.get("username") or "").strip()
            for index, doctor in enumerate(doctors):
                name = str(doctor.get("name") or "")
                if name and (name == display or name in display or display in name):
                    self.reg_doctor.setCurrentIndex(index)
                    self._default_doctor_id = doctor["id"]
                    self._default_doctor_name = name
                    break
        self.reg_doctor.blockSignals(False)
        self._loading_doctors = False
        self.reg_msg.setText(f"医生 {len(doctors)} 位" + (
            "；已优先选中当前登录医生" if self._default_doctor_id else ""
        ))

    def _confirm_doctor_change(self, _index: int) -> None:
        if getattr(self, "_loading_doctors", False):
            return
        default_id = getattr(self, "_default_doctor_id", None)
        current_id = self.reg_doctor.currentData()
        if default_id is None or current_id is None or current_id == default_id:
            return
        current_name = self.reg_doctor.currentText()
        default_name = getattr(self, "_default_doctor_name", "") or "当前登录医生"
        answer = QMessageBox.question(
            self,
            "更换挂号医生",
            f"当前登录医生是 {default_name}。\n\n确认把现场挂号改到 {current_name}？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.reg_doctor.blockSignals(True)
            index = self.reg_doctor.findData(default_id)
            if index >= 0:
                self.reg_doctor.setCurrentIndex(index)
            self.reg_doctor.blockSignals(False)
            return
        # 用户确认后，以新医生为准，避免每次选择都重复弹窗
        self._default_doctor_id = current_id

    def _quick_id_changed(self) -> None:
        digits = self.qr_id_number.text().strip()
        self.qr_birth_age.set_id_number(digits)
        born, _error = parse_id_birth(digits)
        if len(digits) == 18 and born is not None and self.qr_gender.currentData() == "unknown":
            self.qr_gender.setCurrentIndex(
                self.qr_gender.findData("male" if int(digits[16]) % 2 else "female")
            )

    def _quick_create_and_register(self) -> None:
        name = self.qr_name.text().strip()
        phone = self.qr_phone.text().strip()
        if not name or not phone:
            self.reg_msg.setText("快速建档至少填写姓名和手机号")
            return
        register_now = self.qr_mode_register.isChecked()
        doctor_id = None
        if register_now:
            doctor_id = self.reg_doctor.currentData()
            if not doctor_id:
                self._load_registration_doctors()
                doctor_id = self.reg_doctor.currentData()
            if not doctor_id:
                self.reg_msg.setText("立即挂号需要先选择挂号医生")
                return
        id_number = self.qr_id_number.text().strip()
        birth_date = self.qr_birth_age.birth_date_text() or None
        payload = {
            "name": name,
            "gender": self.qr_gender.currentData(),
            "birth_date": birth_date,
            "phone": phone,
            "id_type": "id_card" if id_number else "none",
            "id_number": id_number or None,
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
            registration = (
                self.api.create_registration(patient["id"], doctor_id)
                if register_now
                else None
            )
        except ApiError as e:
            self.reg_msg.setText(f"快速建档失败（{e.status_code}）：{e.detail}")
            return
        self.reg_patient_id.setText(str(patient["id"]))
        self.reg_selected_label.setText(
            f"{patient.get('patient_no') or patient['id']} {patient['name']} · "
            f"{ {'male':'男','female':'女'}.get(patient.get('gender'), '性别不详') }/"
            f"{patient.get('age') if patient.get('age') is not None else '年龄不详'}"
        )
        self.banner.set_patient(patient)
        self.side_info.set_patient(patient)
        if registration is not None:
            self.reg_msg.setText(
                f"快速建档并挂号成功：{patient['name']}，患者号 "
                f"{patient.get('patient_no') or patient['id']}，挂号 ID {registration['id']}；"
                "证件/地址可后补"
            )
        else:
            self.reg_msg.setText(
                f"快速建档成功：{patient['name']}，患者号 "
                f"{patient.get('patient_no') or patient['id']}；已按“仅建档”处理，未挂号"
            )
        self.qr_name.clear()
        self.qr_phone.clear()
        self.qr_id_number.clear()
        self.qr_birth_age.reset()
        self._load_pending_registrations()

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
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        top = QHBoxLayout()
        title = QLabel("待接诊挂号")
        title.setStyleSheet("font-size:15px;font-weight:bold")
        self.reception_count = QLabel("")
        self.reception_count.setStyleSheet("color:#64748b")
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load_pending_registrations)
        top.addWidget(title)
        top.addWidget(self.reception_count)
        top.addStretch(1)
        top.addWidget(refresh)
        left_layout.addLayout(top)

        self.reg_table = QTableWidget(0, 6)
        self.reg_table.setHorizontalHeaderLabels(
            ["挂号", "患者", "性别/年龄", "医生", "分诊", "状态"]
        )
        set_column_layout(self.reg_table, stretch=(1,), contents=(0, 2, 3, 4, 5))
        self.reg_table.cellClicked.connect(self._select_reception_patient)
        left_layout.addWidget(self.reg_table, 1)
        self.reception_empty = QLabel("暂无待接诊挂号")
        self.reception_empty.setAlignment(Qt.AlignCenter)
        self.reception_empty.setStyleSheet("color:#64748b;padding:12px")
        self.reception_empty.setVisible(False)
        left_layout.addWidget(self.reception_empty)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 0, 0, 0)
        box = QGroupBox("接诊详情")
        form = QFormLayout(box)
        self.reg_id = QSpinBox()
        self.reg_id.setRange(0, 10_000_000)
        self.reg_id.setSpecialValueText("请选择挂号")
        self.reg_id.setValue(0)
        self.reception_patient = QLabel("未选择患者")
        self.reception_patient.setWordWrap(True)
        self.reception_patient.setStyleSheet("font-weight:bold")
        start = QPushButton("开始接诊")
        start.clicked.connect(self._start_encounter)
        form.addRow("挂号 ID", self.reg_id)
        form.addRow("患者", self.reception_patient)
        form.addRow("诊断", QLabel("接诊后到「病历」页填写"))
        form.addRow("", start)
        right_layout.addWidget(box)
        self.reception_msg = QLabel("")
        self.reception_msg.setWordWrap(True)
        right_layout.addWidget(self.reception_msg)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 400])
        layout.addWidget(splitter, 1)
        return page

    def _load_pending_registrations(self) -> None:
        try:
            rows = [
                item for item in self.api.doctor_worklist()
                if not item.get("encounter_id")
                and item.get("registration_status") == "registered"
            ]
        except ApiError as e:
            self.reception_msg.setText(f"加载失败：{e.detail}")
            return
        self.pending_registrations = rows
        self.reception_count.setText(f"{len(rows)} 人")
        self.reception_empty.setVisible(not rows)
        self.reg_table.setRowCount(len(rows))
        for index, reg in enumerate(rows):
            gender = {"male": "男", "female": "女"}.get(
                reg.get("gender"), "性别不详"
            )
            age = reg.get("age")
            values = [
                str(reg["registration_id"]),
                reg.get("patient_name") or "",
                f"{gender}/{age if age is not None else '年龄不详'}",
                reg.get("doctor_name") or "",
                f"{reg.get('triage_level') or '—'} 级",
                zh("registration_status", reg.get("registration_status", "")),
            ]
            for col, value in enumerate(values):
                self.reg_table.setItem(index, col, QTableWidgetItem(str(value)))
        if rows:
            self.reg_table.selectRow(0)
            self._select_reception_patient(0, 0)
        else:
            self.reception_patient.setText("未选择患者")

    def _select_reception_patient(self, row: int, _col: int) -> None:
        rows = getattr(self, "pending_registrations", [])
        if not 0 <= row < len(rows):
            return
        item = rows[row]
        self.reg_id.setValue(item["registration_id"])
        gender = {"male": "男", "female": "女"}.get(
            item.get("gender"), "性别不详"
        )
        age = item.get("age")
        self.reception_patient.setText(
            f"{item.get('patient_name') or ''} · {gender}/"
            f"{age if age is not None else '年龄不详'} · "
            f"医生 {item.get('doctor_name') or '—'} · 挂号 {item['registration_id']}"
        )

    def _start_encounter(self) -> None:
        if self.reg_id.value() <= 0:
            self.reception_msg.setText("请先选择待接诊挂号")
            return
        try:
            encounter = self.api.create_encounter(self.reg_id.value())
        except ApiError as e:
            self.reception_msg.setText(f"接诊失败（{e.status_code}）：{e.detail}")
            return
        self.reception_msg.setText(
            f"接诊成功：就诊 ID {encounter['id']}；请到「病历」页填写诊断"
        )
        row = next(
            (
                item
                for item in getattr(self, "pending_registrations", [])
                if item.get("registration_id") == self.reg_id.value()
            ),
            None,
        )
        if row:
            try:
                patient = self.api.get_patient(row["patient_id"])
                self.banner.set_patient(patient, encounter["id"], "已接诊")
                self.patient_info.set_patient(patient, encounter["id"], "已接诊")
                self._active_patient_id = row["patient_id"]
                self._active_patient_name = row.get("patient_name") or ""
                self._clear_side_history()
            except ApiError:
                pass
        self._set_encounter_everywhere(encounter["id"])
        self._set_patient_actions(True)
        self._set_clinical_tabs(True, True)
        self._load_pending_registrations()
        # 接诊成功后跳到病历，保留顶部患者条和左侧患者卡
        self._switch_tab("病历")
        self._load_record()

    # ---------- 病历 ----------
    def _build_record_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        top = QHBoxLayout()
        self.mr_encounter_id = QSpinBox()
        self.mr_encounter_id.setRange(0, 10_000_000)
        self.mr_encounter_id.setSpecialValueText("未接诊")
        self.mr_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.mr_encounter_id.lineEdit().setReadOnly(True)
        self.mr_encounter_id.setFocusPolicy(Qt.NoFocus)
        self.mr_encounter_id.setMinimumWidth(86)
        self.mr_encounter_id.setAlignment(Qt.AlignCenter)
        load = QPushButton("载入病历")
        load.clicked.connect(self._load_record)
        self.mr_encounter_label = self._encounter_label()
        self.mr_encounter_id.hide()
        top.addWidget(QLabel("就诊 ID"))
        top.addWidget(self.mr_encounter_label)
        top.addWidget(load)
        self.record_template = QComboBox()
        self.record_template.addItem("选择病历模板", "")
        self.record_template.addItem("上呼吸道感染", "uri")
        self.record_template.addItem("高血压复诊", "hypertension")
        self.record_template.addItem("伤口换药", "wound")
        apply_template = QPushButton("套用")
        apply_template.clicked.connect(self._apply_record_template)
        top.addWidget(self.record_template)
        top.addWidget(apply_template)
        top.addStretch(1)
        layout.addLayout(top)
        self.record_state = QLabel("")
        self.record_state.setWordWrap(True)
        layout.addWidget(self.record_state)

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
            "treatment_advice": (5, 0),
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

        diagnosis_box = QGroupBox("诊断（病史、查体后填写；结果未回可先记“待查”）")
        diagnosis_layout = QVBoxLayout(diagnosis_box)
        self.record_diagnosis = QLabel("诊断：—")
        self.record_diagnosis.setStyleSheet("font-weight:bold")
        diagnosis_layout.addWidget(self.record_diagnosis)
        hint = QLabel("先完成病史与查体；检验/检查结果未回时可点“暂记待查”，结果回报后修改并保存。")
        hint.setStyleSheet("color:#64748b")
        hint.setWordWrap(True)
        diagnosis_layout.addWidget(hint)
        self.record_diagnosis_editor = DiagnosisEditor()
        diagnosis_layout.addWidget(self.record_diagnosis_editor)
        diag_actions = QHBoxLayout()
        self.record_pending_diag = QPushButton("暂记待查")
        self.record_pending_diag.clicked.connect(self._set_pending_diagnosis)
        self.record_save_diag = QPushButton("保存全部诊断")
        self.record_save_diag.clicked.connect(self._save_record_diagnoses)
        diag_actions.addWidget(self.record_pending_diag)
        diag_actions.addWidget(self.record_save_diag)
        diag_actions.addStretch(1)
        diagnosis_layout.addLayout(diag_actions)
        grid.addWidget(diagnosis_box, 4, 0, 1, 2)
        layout.addLayout(grid, 1)

        buttons = QHBoxLayout()
        self.record_save = QPushButton("保存 / 更新")
        self.record_save.clicked.connect(self._save_record)
        self.record_sign = QPushButton("签名锁定")
        self.record_sign.clicked.connect(self._sign_record)
        self.record_revision = QPushButton("申请修订")
        self.record_revision.clicked.connect(self._request_record_revision)
        quality = QPushButton("质控评分")
        quality.clicked.connect(self._check_quality)
        buttons.addWidget(self.record_save)
        buttons.addWidget(self.record_sign)
        buttons.addWidget(self.record_revision)
        buttons.addWidget(quality)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.record_msg = QLabel("")
        self.record_msg.setWordWrap(True)
        layout.addWidget(self.record_msg)
        # 病历字段多，必须独立滚动，否则会把整个门诊工作站撑到超过 768 高
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(page)
        return scroll

    @staticmethod
    def _encounter_label() -> QLabel:
        label = QLabel("未接诊")
        label.setMinimumWidth(72)
        label.setStyleSheet("font-weight:bold;padding:4px 8px;background:#f8fafc;border:1px solid #dbe7f3;border-radius:5px;")
        return label

    def _set_record_editable(self, editable: bool, signed: bool = False) -> None:
        for edit in getattr(self, "record_edits", {}).values():
            edit.setReadOnly(not editable)
        editor = getattr(self, "record_diagnosis_editor", None)
        if editor is not None and hasattr(editor, "set_read_only"):
            editor.set_read_only(not editable)
        for attr in ("record_save", "record_sign", "record_save_diag", "record_pending_diag"):
            button = getattr(self, attr, None)
            if button is not None:
                button.setEnabled(editable)
        if hasattr(self, "record_revision"):
            self.record_revision.setEnabled(signed)

    def _apply_record_template(self) -> None:
        code = self.record_template.currentData()
        if not code:
            return
        templates = {
            "uri": {
                "chief_complaint": "发热、咳嗽 2 天。",
                "present_illness": "受凉后出现发热，最高 38.3℃，伴咳嗽、咽痛，无胸闷气促。",
                "past_history": "既往体健，否认高血压、糖尿病、肝炎、结核等病史。",
                "personal_history": "否认吸烟、饮酒，否认近期疫区旅居史。",
                "marital_history": "已婚，育有 1 子，配偶及子女体健。",
                "family_history": "否认家族遗传病及传染病史。",
                "physical_exam": "T 38.1℃，P 88 次/分，R 20 次/分，BP 118/76 mmHg。咽充血，双侧扁桃体 I 度肿大，双肺呼吸音清，未闻及干湿啰音。",
                "auxiliary_exam": "血常规：白细胞及中性粒细胞比例升高。",
                "treatment_advice": "1. 对症退热、止咳；2. 多饮水、休息；3. 如持续高热、气促及时复诊。",
            },
            "hypertension": {
                "chief_complaint": "发现血压升高 5 年，头晕 1 周。",
                "present_illness": "高血压病史 5 年，长期口服降压药，近期家庭自测血压 150-160/90-100 mmHg，伴轻度头晕。",
                "past_history": "高血压 5 年，否认糖尿病、冠心病、脑卒中史。",
                "personal_history": "低盐饮食，否认吸烟，偶饮酒。",
                "marital_history": "已婚，育有 1 女。",
                "family_history": "父亲有高血压病史。",
                "physical_exam": "BP 156/96 mmHg，神清，心肺腹查体未见明显异常，双下肢无水肿。",
                "auxiliary_exam": "心电图：窦性心律，左室高电压。",
                "treatment_advice": "1. 调整降压方案；2. 低盐低脂饮食、规律运动；3. 每日家庭自测血压并记录；4. 2 周复诊。",
            },
            "wound": {
                "chief_complaint": "右手指外伤后伤口换药。",
                "present_illness": "右手指外伤清创缝合后第 3 天，伤口无明显红肿渗液，疼痛可耐受。",
                "past_history": "既往体健。",
                "personal_history": "否认吸烟、饮酒。",
                "marital_history": "未婚。",
                "family_history": "无特殊。",
                "physical_exam": "右手食指伤口敷料干燥，周围皮肤无红肿，末梢血运感觉正常。",
                "auxiliary_exam": "无。",
                "treatment_advice": "1. 换药；2. 保持伤口干燥；3. 如红肿渗液及时复诊。",
            },
        }
        values = templates.get(code)
        if not values:
            return
        for key, text in values.items():
            edit = self.record_edits.get(key)
            if edit is not None:
                edit.setPlainText(text)
        self.wb_summary.setText(f"已套用病历模板：{self.record_template.currentText()}")

    def _load_record(self) -> None:
        try:
            record = self.api.get_medical_record(self.mr_encounter_id.value())
            encounter = self.api.get_encounter(self.mr_encounter_id.value())
        except ApiError as e:
            self.record_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        if hasattr(self, "record_diagnosis"):
            prefix = "复诊 · " if encounter.get("visit_type") == "follow_up" else ""
            self.record_diagnosis.setText(
                f"{prefix}诊断：{encounter.get('diagnosis_code') or ''} "
                f"{encounter.get('diagnosis') or '—'}".strip()
            )
        if hasattr(self, "record_diagnosis_editor"):
            try:
                rows = self.api.list_encounter_diagnoses(self.mr_encounter_id.value())
            except ApiError:
                rows = []
            if not rows and encounter.get("diagnosis"):
                rows = [
                    {
                        "diagnosis_code": encounter.get("diagnosis_code") or "",
                        "diagnosis": encounter.get("diagnosis") or "",
                        "diagnosis_type": "primary",
                        "note": "",
                    }
                ]
            self.record_diagnosis_editor.set_items(rows)
        for key, _label, _limit in _RECORD_FIELDS:
            self.record_edits[key].setPlainText(record.get(key) or "")
        signed = bool(record.get("signed_at"))
        closed = encounter.get("status") == "closed"
        self._set_record_editable(not signed and not closed, signed=signed)
        if hasattr(self, "record_state"):
            if signed:
                self.record_state.setText("【只读】病历已签名；可申请修订或全额退费后自动解锁")
                self.record_state.setStyleSheet("color:#b45309;font-weight:bold")
            elif closed:
                self.record_state.setText("【只读】就诊已收费；全额退费后自动重开")
                self.record_state.setStyleSheet("color:#b45309;font-weight:bold")
            else:
                self.record_state.setText("可编辑病历")
                self.record_state.setStyleSheet("color:#64748b")
        if signed:
            self.record_msg.setText(
                f"病历已签名（{record.get('signed_by') or '—'}），当前只读；"
                "可点「申请修订」，审批通过后解锁；全额退费也会自动解锁"
            )
        elif closed:
            self.record_msg.setText("就诊已收费，病历只读；全额退费后自动重开")
        else:
            self.record_msg.setText(
                f"病历可编辑（书写：{record.get('written_by') or '—'}）"
            )

    def _set_pending_diagnosis(self) -> None:
        if self.record_diagnosis_editor.get_items():
            self.record_msg.setText("已有诊断；如需改为待查，请先在诊断表中删除或修改原诊断")
            return
        self.record_diagnosis_editor.add_pending_diagnosis()
        self.record_msg.setText("已暂记“待查”；拿到检验/检查结果后请修改诊断并保存")
        self._save_record_diagnoses()

    def _save_record_diagnoses(self) -> None:
        encounter_id = self.mr_encounter_id.value()
        if not encounter_id:
            self.record_msg.setText("请先载入病历")
            return
        items = self.record_diagnosis_editor.get_items()
        if not items:
            self.record_msg.setText("至少填写一条诊断")
            return
        try:
            rows = self.api.save_encounter_diagnoses(encounter_id, items)
        except ApiError as e:
            self.record_msg.setText(f"诊断保存失败（{e.status_code}）：{e.detail}")
            return
        primary = rows[0] if rows else {}
        self.record_diagnosis.setText(
            f"主诊断：{primary.get('diagnosis_code') or ''} "
            f"{primary.get('diagnosis') or '—'}（共 {len(rows)} 条）"
        )
        self.record_msg.setText(f"诊断已保存：{len(rows)} 条，第一条为主诊断")

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

    def _request_record_revision(self) -> None:
        encounter_id = self.mr_encounter_id.value()
        if not encounter_id:
            self.record_msg.setText("请先选择就诊")
            return
        reason, ok = QInputDialog.getText(
            self, "申请病历修订", "修订理由（提交后由管理员/院长审批）："
        )
        if not ok or not reason.strip():
            return
        try:
            row = self.api.request_record_revision(encounter_id, reason.strip())
        except ApiError as e:
            self.record_msg.setText(f"申请失败（{e.status_code}）：{e.detail}")
            return
        self.record_msg.setText(
            f"修订申请已提交（#{row['id']}，{row['status']}），等待审批"
        )

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
        self.history_id_number.setPlaceholderText("身份证号（仅检索，不显示）")
        search = QPushButton("查询患者")
        search.clicked.connect(self._search_history_patients)
        row.addWidget(QLabel("姓名"))
        row.addWidget(self.history_name)
        row.addWidget(QLabel("身份证号"))
        row.addWidget(self.history_id_number)
        row.addWidget(search)
        layout.addLayout(row)

        self.history_patient_table = QTableWidget(0, 3)
        self.history_patient_table.setHorizontalHeaderLabels(
            ["患者编号", "姓名", "性别/年龄"]
        )
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
        self.history_lab_table.cellDoubleClicked.connect(self._show_lab_trend)
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
        self.history_search_patients = patients
        self.history_patient_table.setRowCount(len(patients))
        for row, patient in enumerate(patients):
            gender = {"male": "男", "female": "女"}.get(
                patient.get("gender"), "性别不详"
            )
            age = patient.get("age")
            values = [
                patient.get("patient_no") or str(patient["id"]),
                patient["name"],
                f"{gender}/{age if age is not None else '年龄不详'}",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 0:
                    cell.setData(Qt.UserRole, patient["id"])
                self.history_patient_table.setItem(row, col, cell)
        self.history_msg.setText(f"共 {len(patients)} 位患者，点击选择查看历史")

    def _select_history_patient(self, row: int, _col: int) -> None:
        item = self.history_patient_table.item(row, 0)
        if item:
            patient_id = item.data(Qt.UserRole)
            if patient_id is not None:
                self._load_history(int(patient_id))

    def _load_history(self, patient_id: int) -> None:
        try:
            data = self.api.get_patient_history(patient_id)
        except ApiError as e:
            self.history_msg.setText(f"加载历史失败（{e.status_code}）：{e.detail}")
            return
        self.history_data = data
        patient = data["patient"]
        self.history_patient_label.setText(
            f"患者：{patient.get('patient_no') or patient['id']} "
            f"{patient['name']}  历史就诊 {len(data['encounters'])} 次"
        )
        self.history_msg.setText("点击就诊行查看详情；双击检验行查看同名项目趋势")
        self.history_patient_table.setRowCount(1)
        gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "性别不详")
        age = patient.get("age")
        self.history_patient_table.setItem(
            0, 0, QTableWidgetItem(str(patient.get("patient_no") or patient["id"]))
        )
        self.history_patient_table.setItem(0, 1, QTableWidgetItem(patient["name"]))
        self.history_patient_table.setItem(
            0, 2, QTableWidgetItem(f"{gender}/{age if age is not None else '年龄不详'}")
        )
        self.history_patient_table.selectRow(0)
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

    def _show_lab_trend(self, row: int, _col: int) -> None:
        rows = getattr(self, "history_lab_rows", [])
        if not 0 <= row < len(rows):
            return
        item = rows[row]
        name = item.get("item_name") or ""
        history = getattr(self, "history_data", {}).get("encounters", [])
        values = []
        numeric: list[tuple[str, float]] = []
        unit = ""
        reference_low = None
        reference_high = None
        for encounter in history:
            for lab in encounter.get("lab_requests", []):
                if (lab.get("item_name") or "") != name:
                    continue
                result = (
                    f"{lab['result_value']:g} {lab.get('result_unit') or ''}".strip()
                    if lab.get("result_value") is not None
                    else lab.get("result") or "—"
                )
                unit = lab.get("result_unit") or unit
                if lab.get("reference_low") is not None and reference_low is None:
                    reference_low = float(lab["reference_low"])
                if lab.get("reference_high") is not None and reference_high is None:
                    reference_high = float(lab["reference_high"])
                if lab.get("result_value") is not None:
                    numeric.append((str(encounter.get("visited_at") or "")[:10], float(lab["result_value"])))
                values.append(
                    (
                        str(encounter.get("visited_at") or "")[:10],
                        result,
                        f"{lab.get('reference_low') or '—'}–{lab.get('reference_high') or '—'}",
                        {"H": "偏高", "L": "偏低", "N": "正常"}.get(
                            lab.get("abnormal_flag") or "", "—"
                        ),
                    )
                )
        dialog = QDialog(self)
        dialog.setWindowTitle(f"检验趋势 · {name}")
        dialog.resize(700, 520)
        layout = QVBoxLayout(dialog)
        if numeric:
            layout.addWidget(
                TrendChart(
                    [item[0] for item in numeric],
                    [item[1] for item in numeric],
                    unit,
                    reference_low,
                    reference_high,
                )
            )
        table = QTableWidget(len(values), 4)
        table.setHorizontalHeaderLabels(["日期", "结果", "参考范围", "异常"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, row_values in enumerate(values):
            for j, value in enumerate(row_values):
                table.setItem(i, j, QTableWidgetItem(str(value)))
        layout.addWidget(table)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

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
        self.history_lab_rows = encounter["lab_requests"]
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
        self.rx_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.rx_encounter_id.lineEdit().setReadOnly(True)
        self.rx_encounter_id.setFocusPolicy(Qt.NoFocus)
        load = QPushButton("刷新药品目录")
        load.clicked.connect(self._load_drugs)
        self.rx_encounter_label = self._encounter_label()
        self.rx_encounter_id.hide()
        top.addWidget(QLabel("就诊 ID"))
        top.addWidget(self.rx_encounter_label)
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
        suggest_drug = QPushButton("建议新增药品")
        suggest_drug.clicked.connect(lambda: self._suggest_catalog("drug"))
        top.addWidget(suggest_drug)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Vertical)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 16, 0)
        left_title = QLabel("药品目录（只读，双击加入处方）")
        left_title.setStyleSheet("font-weight:bold")
        left_layout.addWidget(left_title)
        self.drug_table = QTableWidget(0, 8)
        self.drug_table.setHorizontalHeaderLabels(
            ["ID", "药品", "规格", "单价", "库存", "自费约", "医保比例", "医保类别"]
        )
        if not self.insurance_enabled:
            self.drug_table.setColumnHidden(6, True)
            self.drug_table.setColumnHidden(7, True)
        set_column_layout(
            self.drug_table, stretch=(1, 2), contents=(0, 3, 4, 5, 6, 7)
        )
        self.drug_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.drug_table.cellClicked.connect(self._catalog_clicked)
        self.drug_table.cellDoubleClicked.connect(self._catalog_double_clicked)
        left_layout.addWidget(self.drug_table, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 8, 0, 0)
        rx_title = QLabel("处方")
        rx_title.setStyleSheet("font-weight:bold")
        right_layout.addWidget(rx_title)
        self.rx_table = QTableWidget(0, 6)
        self.rx_table.setHorizontalHeaderLabels(
            ["药品", "数量", "单价", "用法", "金额", "状态"]
        )
        set_column_layout(self.rx_table, stretch=(0, 3), contents=(1, 2, 4, 5))
        right_layout.addWidget(self.rx_table, 1)
        rx_actions = QHBoxLayout()
        self.rx_edit = QPushButton("编辑选中处方")
        self.rx_edit.clicked.connect(self._edit_selected_rx)
        self.rx_delete = QPushButton("删除选中处方")
        self.rx_delete.clicked.connect(self._delete_selected_rx)
        rx_actions.addStretch(1)
        rx_actions.addWidget(self.rx_edit)
        rx_actions.addWidget(self.rx_delete)
        right_layout.addLayout(rx_actions)
        self.rx_msg = QLabel("")
        self.rx_msg.setWordWrap(True)
        right_layout.addWidget(self.rx_msg)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([560, 300])
        layout.addWidget(splitter, 1)

        rx_tabs = QTabWidget()
        rx_tabs.addTab(page, "西药 / 中成药 / 注射")
        rx_tabs.addTab(self._build_tcm_prescription_page(), "中药饮片")
        rx_tabs.addTab(self._build_tcm_injection_page(), "中药注射")
        rx_tabs.addTab(self._build_prescription_center_page(), "处方中心")
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
        left_layout.setContentsMargins(0, 0, 12, 0)
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
        right_layout.setContentsMargins(12, 0, 0, 0)
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
        # 剂量需要医生直接修改；其余业务表格仍由全局策略设为只读
        self.tcm_table.setProperty("allow_cell_edit", True)
        self.tcm_table.setProperty("editable_columns", (2,))
        self.tcm_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
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
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([460, 700])
        layout.addWidget(splitter, 1)
        self.tcm_items: list[dict] = []
        return page

    def _build_prescription_center_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        title = QLabel("本次诊疗处方中心")
        title.setStyleSheet("font-size:15px;font-weight:bold")
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._refresh_prescription_center)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(refresh)
        layout.addLayout(top)
        hint = QLabel("只读汇总：西药/中成药处方、中药饮片、治疗单")
        hint.setStyleSheet("color:#64748b;")
        layout.addWidget(hint)
        self.rx_center_table = QTableWidget(0, 5)
        self.rx_center_table.setHorizontalHeaderLabels(
            ["类别", "单据号/项目", "状态", "内容", "审核"]
        )
        self.rx_center_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rx_center_table.cellDoubleClicked.connect(self._open_center_row)
        layout.addWidget(self.rx_center_table, 1)
        actions = QHBoxLayout()
        self.rx_center_print = QPushButton("打印选中处方")
        self.rx_center_print.clicked.connect(self._print_center_prescription)
        self.rx_center_edit = QPushButton("编辑选中处方")
        self.rx_center_edit.clicked.connect(self._edit_center_prescription)
        self.rx_center_upload = QPushButton("上传选中处方医保")
        self.rx_center_upload.clicked.connect(self._upload_center_prescription)
        actions.addStretch(1)
        actions.addWidget(self.rx_center_edit)
        actions.addWidget(self.rx_center_upload)
        actions.addWidget(self.rx_center_print)
        layout.addLayout(actions)
        self.rx_center_msg = QLabel("")
        layout.addWidget(self.rx_center_msg)
        return page

    def _refresh_prescription_center(self) -> None:
        table = getattr(self, "rx_center_table", None)
        encounter_id = self.rx_encounter_id.value()
        if table is None or not encounter_id:
            return
        try:
            data = self.api.prescription_center(encounter_id)
        except ApiError as e:
            self.rx_center_msg.setText(f"加载失败：{e.detail}")
            return
        rows = []
        self.rx_center_rows = []
        for row in data.get("western", []):
            self.rx_center_rows.append({"kind": "western", "id": row.get("id")})
            rows.append(
                (
                    "西药/中成药" if row.get("type") == "western" else row.get("type"),
                    row.get("prescription_no") or "",
                    RX_STATUS_LABELS.get(row.get("status"), row.get("status") or ""),
                    f"{row.get('item_count', 0)} 种",
                    row.get("reviewed_by") or "未审",
                )
            )
        for row in data.get("tcm", []):
            self.rx_center_rows.append({"kind": "tcm", "id": row.get("id")})
            rows.append(
                (
                    "中药饮片",
                    row.get("prescription_no") or "",
                    TCM_STATUS_LABELS.get(row.get("status"), row.get("status") or ""),
                    f"{row.get('formula_name') or '方剂'} / {row.get('item_count', 0)} 味",
                    "中药房",
                )
            )
        for row in data.get("treatments", []):
            self.rx_center_rows.append({"kind": "treatment", "id": row.get("id")})
            rows.append(
                (
                    "治疗/处置",
                    row.get("item_name") or "",
                    TREATMENT_STATUS_LABELS.get(row.get("status"), row.get("status") or ""),
                    f"×{row.get('quantity', 1)}",
                    "治疗室",
                )
            )
        table.setRowCount(len(rows))
        for i, values in enumerate(rows):
            for j, value in enumerate(values):
                table.setItem(i, j, QTableWidgetItem(str(value)))
        self.rx_center_msg.setText(f"共 {len(rows)} 张处方/治疗单")

    def _open_center_row(self, row: int, _col: int) -> None:
        rows = getattr(self, "rx_center_rows", [])
        if not 0 <= row < len(rows):
            return
        kind = rows[row]["kind"]
        if kind == "western":
            self.rx_type_tabs.setCurrentIndex(0)
            self.rx_center_msg.setText("已切换到西药处方页，可继续查看/删除明细")
        elif kind == "tcm":
            self.rx_type_tabs.setCurrentIndex(1)
            self.rx_center_msg.setText("已切换到中药饮片页")
        else:
            self.rx_center_msg.setText("治疗单请到治疗室工作站处理")

    def _print_center_prescription(self) -> None:
        row = self.rx_center_table.currentRow()
        rows = getattr(self, "rx_center_rows", [])
        if not 0 <= row < len(rows):
            self.rx_center_msg.setText("请先选择一张处方")
            return
        target = rows[row]
        if target["kind"] != "western":
            self.rx_center_msg.setText("中药/治疗单请在对应页签打印")
            return
        open_print_preview(
            self,
            self.api.prescription_header_print_url(target["id"]),
            "单张处方打印预览",
        )

    def _edit_center_prescription(self) -> None:
        row = self.rx_center_table.currentRow()
        rows = getattr(self, "rx_center_rows", [])
        if not 0 <= row < len(rows):
            self.rx_center_msg.setText("请先选择一张处方")
            return
        target = rows[row]
        if target["kind"] != "western":
            self.rx_center_msg.setText("中药/治疗单请在对应页签编辑")
            return
        dialog = PrescriptionEditDialog(
            self.api, self.rx_encounter_id.value(), target["id"], self
        )
        dialog.exec()
        self._refresh_prescriptions()
        self._refresh_prescription_center()

    def _upload_center_prescription(self) -> None:
        row = self.rx_center_table.currentRow()
        rows = getattr(self, "rx_center_rows", [])
        if not 0 <= row < len(rows):
            self.rx_center_msg.setText("请先选择一张处方")
            return
        target = rows[row]
        if target["kind"] != "western":
            self.rx_center_msg.setText("仅西药/中成药处方支持医保逐张上传")
            return
        try:
            self.api.upload_prescription_insurance(
                self.rx_encounter_id.value(), target["id"]
            )
        except ApiError as e:
            self.rx_center_msg.setText(f"上传失败：{e.detail}")
            return
        self.rx_center_msg.setText("已按处方头上传医保")
        self._refresh_prescription_center()

    def _build_tcm_injection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        title = QLabel("中药注射剂目录")
        title.setStyleSheet("font-weight:bold")
        refresh = QPushButton("刷新注射剂目录")
        refresh.clicked.connect(self._load_tcm_injection_drugs)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(refresh)
        layout.addLayout(top)
        hint = QLabel("按剂型/名称筛选中成药注射剂；需在药品目录维护规范名称。双击加入处方。")
        hint.setStyleSheet("color:#64748b;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Vertical)
        catalog = QWidget()
        catalog_layout = QVBoxLayout(catalog)
        catalog_layout.setContentsMargins(0, 0, 0, 8)
        self.tcm_inj_table = QTableWidget(0, 5)
        self.tcm_inj_table.setHorizontalHeaderLabels(["ID", "药品", "规格", "剂型", "单价"])
        self.tcm_inj_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tcm_inj_table.cellDoubleClicked.connect(self._tcm_inj_double_clicked)
        catalog_layout.addWidget(self.tcm_inj_table, 1)
        splitter.addWidget(catalog)

        rx_box = QWidget()
        rx_layout = QVBoxLayout(rx_box)
        rx_layout.setContentsMargins(0, 8, 0, 0)
        rx_layout.addWidget(QLabel("中药注射处方"))
        self.tcm_inj_rx_table = QTableWidget(0, 4)
        self.tcm_inj_rx_table.setHorizontalHeaderLabels(["药品", "数量", "单价", "天数"])
        self.tcm_inj_rx_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rx_layout.addWidget(self.tcm_inj_rx_table, 1)
        self.tcm_inj_msg = QLabel("")
        self.tcm_inj_msg.setWordWrap(True)
        rx_layout.addWidget(self.tcm_inj_msg)
        splitter.addWidget(rx_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([430, 260])
        layout.addWidget(splitter, 1)
        return page

    def _load_tcm_injection_drugs(self) -> None:
        if not hasattr(self, "drug_rows"):
            self._load_drugs()
        rows = [
            drug
            for drug in getattr(self, "drug_rows", [])
            if self._is_tcm_injection(drug)
        ]
        self.tcm_inj_rows = rows
        if not hasattr(self, "tcm_inj_table"):
            return
        self.tcm_inj_table.setRowCount(len(rows))
        for row, drug in enumerate(rows):
            values = (
                str(drug["id"]),
                drug.get("name") or "",
                drug.get("spec") or "—",
                drug.get("dosage_form") or "—",
                f"{float(drug.get('base_price') or 0):.2f}",
            )
            for col, value in enumerate(values):
                self.tcm_inj_table.setItem(row, col, QTableWidgetItem(value))
        self.tcm_inj_msg.setText(f"注射剂 {len(rows)} 种")
        self._refresh_injection_rx()

    def _tcm_inj_double_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(getattr(self, "tcm_inj_rows", [])):
            self._quick_add_drug(self.tcm_inj_rows[row]["id"])

    def _on_rx_type_changed(self, index: int) -> None:
        if index == 3:
            self._refresh_prescription_center()
        elif index == 2:
            self._load_tcm_injection_drugs()
        elif not hasattr(self, "tcm_herb_rows"):
            self._load_tcm_herbs()

    def _suggest_catalog(self, kind: str) -> None:
        dialog = CatalogProposalDialog(kind, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            row = self.api.create_catalog_proposal(dialog.payload())
        except ApiError as e:
            QMessageBox.warning(self, "提交失败", f"{e.status_code}：{e.detail}")
            return
        QMessageBox.information(
            self,
            "建议已提交",
            f"建议编号 {row['id']} 已提交。\n"
            "药品：药事审核 → 库房审核；治疗项目：院长审批。\n"
            "医生不能直接修改目录。",
        )

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
            name = str(drug.get("name") or "")
            spec = str(drug.get("spec") or "")
            search_text = f"{name}{spec}"
            if lazy_pinyin is not None:
                try:
                    search_text += "".join(lazy_pinyin(name))
                    search_text += "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))
                except Exception:
                    pass
            self.drug_rows.append(
                {
                    **drug,
                    "search_text": search_text.lower(),
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
                if term in str(drug.get("search_text") or drug.get("name", "")).lower()
                or term in str(drug.get("name", "")).lower()
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

    def _is_tcm_injection(self, drug: dict) -> bool:
        text = f"{drug.get('name') or ''}{drug.get('dosage_form') or ''}"
        return "注射" in text and any(
            key in text
            for key in (
                "注射液",
                "注射用",
                "丹参",
                "参麦",
                "血必净",
                "喜炎平",
                "醒脑静",
                "银杏",
                "黄芪",
                "生脉",
                "热毒宁",
                "痰热清",
            )
        )

    def _quick_add_drug(self, drug_id: int) -> None:
        encounter_id = self.rx_encounter_id.value()
        if not encounter_id:
            msg = "请先选择已接诊患者"
            self.rx_msg.setText(msg)
            if hasattr(self, "tcm_inj_msg"):
                self.tcm_inj_msg.setText(msg)
            return
        drug = next(
            (x for x in getattr(self, "drug_rows", []) if x["id"] == drug_id),
            None,
        )
        if drug is None:
            return
        if int(drug.get("stock") or 0) <= 0:
            self.rx_msg.setText(f"{drug.get('name')} 当前库存为 0，不能开方；请先请领")
            return
        dialog = PrescriptionQuickDialog(drug, self)
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.payload()
        stock = int(drug.get("stock") or 0)
        if payload["quantity"] > stock:
            self.rx_msg.setText(
                f"{drug.get('name')} 库存仅 {stock}，开方数量 {payload['quantity']}，请先请领或调整数量"
            )
            return
        try:
            item = self.api.add_prescription(encounter_id, payload)
        except ApiError as e:
            self.rx_msg.setText(f"加入处方失败（{e.status_code}）：{e.detail}")
            return
        status_text = {
            "pending_review": "待药师审核后发药",
            "approved": "已审方",
            "rejected": "已退回",
        }.get(item.get("prescription_status"), item.get("prescription_status") or "")
        self.rx_msg.setText(
            f"已加入处方：{item['drug_name']} × {item['quantity']}（{status_text}）"
        )
        if hasattr(self, "tcm_inj_msg"):
            self.tcm_inj_msg.setText(
                f"已加入处方：{item['drug_name']} × {item['quantity']}"
            )
        self._refresh_prescriptions()

    def _catalog_clicked(self, row: int, _col: int) -> None:
        # 单击只选中，双击才入方，避免误触
        pass

    def _catalog_double_clicked(self, row: int, _col: int) -> None:
        cell = self.drug_table.item(row, 0)
        if cell:
            self._quick_add_drug(int(cell.text()))

    def _refresh_injection_rx(self) -> None:
        table = getattr(self, "tcm_inj_rx_table", None)
        if table is None:
            return
        injection_ids = {
            drug["id"]
            for drug in getattr(self, "drug_rows", [])
            if self._is_tcm_injection(drug)
        }
        rows = [
            item
            for item in getattr(self, "rx_rows", [])
            if item.get("drug_id") in injection_ids
        ]
        table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = (
                item.get("drug_name") or "",
                str(item.get("quantity") or ""),
                f"{item.get('unit_price', 0):.2f}",
                str(item.get("days") or ""),
            )
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))

    def _refresh_prescriptions(self) -> None:
        try:
            items = self.api.list_prescriptions(self.rx_encounter_id.value())
        except ApiError:
            return
        self.rx_rows = items
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
            status = {
                "pending_review": "待审方",
                "approved": "已审方",
                "rejected": "已退回",
                "dispensing": "调配中",
                "dispensed": "已发药",
                "cancelled": "已作废",
            }.get(item.get("prescription_status"), item.get("prescription_status") or "")
            self.rx_table.setItem(row, 5, QTableWidgetItem(status))
        if not items:
            self.rx_msg.setText("当前没有处方；双击左侧药品加入")
        self._refresh_injection_rx()
        self._refresh_prescription_center()

    def _edit_selected_rx(self) -> None:
        row = self.rx_table.currentRow()
        items = getattr(self, "rx_rows", [])
        if not 0 <= row < len(items):
            self.rx_msg.setText("请先选择一条本次处方")
            return
        item = items[row]
        prescription_id = item.get("prescription_id")
        if not prescription_id:
            self.rx_msg.setText("该明细没有处方头，不能编辑")
            return
        dialog = PrescriptionEditDialog(
            self.api, self.rx_encounter_id.value(), int(prescription_id), self
        )
        dialog.exec()
        self._refresh_prescriptions()

    def _delete_selected_rx(self) -> None:
        row = self.rx_table.currentRow()
        items = getattr(self, "rx_rows", [])
        if not 0 <= row < len(items):
            self.rx_msg.setText("请先选择一条本次处方")
            return
        item = items[row]
        if QMessageBox.question(
            self, "删除处方", f"确认删除 {item.get('drug_name') or '该药品'}？"
        ) != QMessageBox.Yes:
            return
        try:
            self.api.delete_prescription(self.rx_encounter_id.value(), item["id"])
        except ApiError as e:
            self.rx_msg.setText(f"删除失败（{e.status_code}）：{e.detail}")
            return
        self.rx_msg.setText("处方已删除，对应未收费费用已同步取消")
        self._refresh_prescriptions()

    # ---------- 检验 / 检查 ----------
    def _build_exam_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.exam_encounter_id = QSpinBox()
        self.exam_encounter_id.setRange(0, 10_000_000)
        self.exam_encounter_id.setSpecialValueText("未接诊")
        self.exam_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.exam_encounter_id.lineEdit().setReadOnly(True)
        self.exam_encounter_id.setFocusPolicy(Qt.NoFocus)
        row = QHBoxLayout()
        self.exam_encounter_label = self._encounter_label()
        self.exam_encounter_id.hide()
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.exam_encounter_label)
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
        cancel_request = QPushButton("取消选中检验/检查")
        cancel_request.clicked.connect(self._cancel_exam)
        list_row.addStretch(1)
        list_row.addWidget(cancel_request)
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
        self.exam_rows = []
        try:
            for request in self.api.list_lab_requests(encounter_id):
                self.exam_rows.append({"kind": "lab", "id": request.get("id")})
                rows.append(
                    (
                        "检验",
                        request.get("item_name") or "",
                        zh("lab_status", request.get("status")),
                        request.get("result") or "",
                        str(
                            request.get("reported_at")
                            or request.get("requested_at")
                            or ""
                        )[:16].replace("T", " "),
                    )
                )
            for request in self.api.list_imaging_requests(encounter_id):
                self.exam_rows.append({"kind": "imaging", "id": request.get("id")})
                rows.append(
                    (
                        "检查",
                        request.get("item_name") or "",
                        zh("lab_status", request.get("status")),
                        request.get("report") or request.get("result") or "",
                        str(
                            request.get("reported_at")
                            or request.get("requested_at")
                            or ""
                        )[:16].replace("T", " "),
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
        self.treat_rows = rows
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

    def _cancel_exam(self) -> None:
        row = self.exam_table.currentRow()
        rows = getattr(self, "exam_rows", [])
        if not (0 <= row < len(rows)):
            self.exam_msg.setText("请先选择一条检验/检查")
            return
        item = rows[row]
        label = "检验" if item["kind"] == "lab" else "检查"
        if QMessageBox.question(
            self, f"取消{label}", f"确认取消这条{label}？未收费费用会同步取消"
        ) != QMessageBox.Yes:
            return
        try:
            if item["kind"] == "lab":
                self.api.cancel_lab_request(item["id"])
            else:
                self.api.cancel_imaging_request(item["id"])
        except ApiError as e:
            self.exam_msg.setText(f"取消失败（{e.status_code}）：{e.detail}")
            return
        self.exam_msg.setText(f"{label}已取消")
        self._refresh_exam_requests()

    def _cancel_treatment_order(self) -> None:
        row = self.treat_table.currentRow()
        rows = getattr(self, "treat_rows", [])
        if not (0 <= row < len(rows)):
            self.treat_msg.setText("请先选择一条治疗单")
            return
        order = rows[row]
        if order.get("status") != "pending":
            self.treat_msg.setText("只有待执行的治疗单可以取消")
            return
        if QMessageBox.question(
            self, "取消治疗", f"确认取消 {order.get('item_name') or '该治疗'}？"
        ) != QMessageBox.Yes:
            return
        try:
            self.api.cancel_treatment(order["id"])
        except ApiError as e:
            self.treat_msg.setText(f"取消失败（{e.status_code}）：{e.detail}")
            return
        self.treat_msg.setText("治疗单已取消")
        self._refresh_treatments()

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
        self.treat_encounter_id.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.treat_encounter_id.lineEdit().setReadOnly(True)
        self.treat_encounter_id.setFocusPolicy(Qt.NoFocus)
        self.treat_combo = QComboBox()
        self.treat_quantity = QSpinBox()
        self.treat_quantity.setRange(1, 100)
        self.treat_note = QLineEdit()
        self.treat_note.setPlaceholderText("如：头孢曲松 2g 静滴")
        load = QPushButton("刷新治疗项目")
        load.clicked.connect(self._load_treatment_items)
        submit = QPushButton("开治疗单")
        submit.clicked.connect(self._create_treatment)
        self.treat_encounter_label = self._encounter_label()
        self.treat_encounter_id.hide()
        form.addRow("就诊 ID", self.treat_encounter_label)
        form.addRow("治疗项目", self.treat_combo)
        form.addRow("数量", self.treat_quantity)
        form.addRow("备注", self.treat_note)
        suggest = QPushButton("建议新增治疗项目")
        suggest.clicked.connect(lambda: self._suggest_catalog("treatment"))
        form.addRow("", load)
        form.addRow("", suggest)
        form.addRow("", submit)
        layout.addWidget(box)

        self.treat_msg = QLabel("")
        self.treat_msg.setWordWrap(True)
        layout.addWidget(self.treat_msg)

        list_row = QHBoxLayout()
        list_row.addWidget(QLabel("本次已开治疗"))
        refresh_list = QPushButton("刷新已开治疗")
        refresh_list.clicked.connect(self._refresh_treatments)
        cancel_order = QPushButton("取消选中治疗")
        cancel_order.clicked.connect(self._cancel_treatment_order)
        list_row.addStretch(1)
        list_row.addWidget(cancel_order)
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

