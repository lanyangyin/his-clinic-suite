"""中药处方 + 中药房 + 煎药室。"""
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
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
from his_client.ui.theme import apply_theme
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.patient_banner import PatientBanner

SPECIAL = {
    "none": "常规",
    "first": "先煎",
    "last": "后下",
    "wrap": "包煎",
    "separate": "另煎",
    "melt": "烊化",
    "infuse": "冲服",
}
P_STATUS = {
    "pending": "待审核",
    "reviewed": "已审核",
    "dispensed": "已发药",
    "decocting": "煎药中",
    "completed": "已完成",
    "cancelled": "已取消",
}
D_STATUS = {
    "received": "已接方",
    "soaking": "浸泡中",
    "decocting": "煎煮中",
    "completed": "已包装",
    "issued": "已发放",
}


class TcmWidget(QWidget):
    def __init__(self, api: ApiClient, role: str = "doctor", parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.role = role
        self.items: list[dict] = []
        self.banner = PatientBanner()
        tabs = SidebarTabs()
        if role in ("doctor", "admin"):
            tabs.addTab(self._build_prescribe_tab(), "开中药方")
        if role in ("pharmacist", "admin"):
            tabs.addTab(self._build_pharmacy_tab(), "中药房")
        if role in ("pharmacist", "decoction", "admin"):
            tabs.addTab(self._build_decoction_tab(), "煎药室")
        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        layout.addWidget(tabs)

    def _load_encounter_context(self) -> None:
        encounter_id = self.encounter_id.value()
        if not encounter_id:
            self.banner.clear()
            return
        try:
            summary = self.api.encounter_summary(encounter_id)
        except ApiError:
            self.banner.clear()
            return
        self.banner.set_patient(
            {
                "id": summary.get("patient_id"),
                "patient_no": summary.get("patient_no"),
                "name": summary.get("patient_name"),
                "gender": summary.get("gender"),
                "age": summary.get("age"),
                "allergy_label": summary.get("allergy_label"),
                "phone": summary.get("phone"),
            },
            encounter_id,
            {"open": "接诊中", "paused": "已挂起", "closed": "已收费"}.get(
                summary.get("status") or "", summary.get("status") or ""
            ),
        )

    # ---------- 医生开方 ----------
    def _build_prescribe_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        head = QGroupBox("处方信息")
        form = QFormLayout(head)
        self.encounter_id = QSpinBox()
        self.encounter_id.setRange(1, 10_000_000)
        self.formula = QLineEdit()
        self.formula.setPlaceholderText("如 桂枝汤")
        self.usage = QComboBox()
        self.usage.addItem("内服", "internal")
        self.usage.addItem("外用", "external")
        self.packs = QSpinBox()
        self.packs.setRange(1, 100)
        self.packs.setValue(3)
        self.service = QComboBox()
        self.service.addItem("代煎", "decoct")
        self.service.addItem("自煎", "self")
        self.method = QLineEdit("常规煎煮")
        self.presc_note = QLineEdit()
        self.encounter_id.editingFinished.connect(self._load_encounter_context)
        form.addRow("就诊 ID", self.encounter_id)
        form.addRow("方名", self.formula)
        form.addRow("用法", self.usage)
        form.addRow("剂数", self.packs)
        form.addRow("煎药方式", self.service)
        form.addRow("煎法", self.method)
        form.addRow("备注", self.presc_note)
        layout.addWidget(head)

        herb_box = QGroupBox("选择饮片")
        herb_layout = QVBoxLayout(herb_box)
        search_row = QHBoxLayout()
        self.herb_search = QLineEdit()
        self.herb_search.setPlaceholderText("饮片名称")
        search = QPushButton("查询饮片")
        search.clicked.connect(self._load_herbs)
        search_row.addWidget(self.herb_search)
        search_row.addWidget(search)
        herb_layout.addLayout(search_row)
        self.herb_table = QTableWidget(0, 3)
        self.herb_table.setHorizontalHeaderLabels(["饮片", "元/克", "毒性"])
        herb_layout.addWidget(self.herb_table)
        add_row = QHBoxLayout()
        self.dose = QDoubleSpinBox()
        self.dose.setRange(0.1, 1000)
        self.dose.setValue(9)
        self.dose.setSuffix(" g")
        self.special = QComboBox()
        for value, label in SPECIAL.items():
            self.special.addItem(label, value)
        add = QPushButton("加入处方")
        add.clicked.connect(self._add_item)
        add_row.addWidget(QLabel("剂量"))
        add_row.addWidget(self.dose)
        add_row.addWidget(self.special)
        add_row.addWidget(add)
        herb_layout.addLayout(add_row)
        layout.addWidget(herb_box)

        selected_box = QGroupBox("处方饮片")
        selected_layout = QVBoxLayout(selected_box)
        self.selected_table = QTableWidget(0, 3)
        self.selected_table.setHorizontalHeaderLabels(["饮片", "剂量(g)", "特殊煎法"])
        selected_layout.addWidget(self.selected_table)
        remove = QPushButton("移除选中")
        remove.clicked.connect(self._remove_item)
        selected_layout.addWidget(remove)
        layout.addWidget(selected_box)

        submit = QPushButton("提交中药处方")
        submit.clicked.connect(self._submit)
        layout.addWidget(submit)
        self.presc_msg = QLabel("")
        self.presc_msg.setWordWrap(True)
        layout.addWidget(self.presc_msg)

        self.my_table = QTableWidget(0, 6)
        self.my_table.setHorizontalHeaderLabels(
            ["处方号", "就诊", "方名", "剂数", "状态", "金额"]
        )
        layout.addWidget(self.my_table)
        refresh = QPushButton("刷新我的中药处方")
        refresh.clicked.connect(self._load_my)
        layout.addWidget(refresh)
        return page

    def _load_herbs(self) -> None:
        try:
            herbs = self.api.list_tcm_herbs()
        except ApiError as e:
            self.presc_msg.setText(f"加载饮片失败（{e.status_code}）：{e.detail}")
            return
        keyword = self.herb_search.text().strip()
        self.herb_rows = [
            herb for herb in herbs if not keyword or keyword in herb["name"]
        ]
        self.herb_table.setRowCount(len(self.herb_rows))
        for row, herb in enumerate(self.herb_rows):
            values = [herb["name"], f"{herb['price_per_g']:.3f}", herb["toxicity"]]
            for col, value in enumerate(values):
                self.herb_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _add_item(self) -> None:
        row = self.herb_table.currentRow()
        if row < 0:
            self.presc_msg.setText("请先选择一味饮片")
            return
        herb = self.herb_rows[row]
        self.items.append(
            {
                "herb_id": herb["id"],
                "herb_name": herb["name"],
                "dose_g": self.dose.value(),
                "special": self.special.currentData(),
            }
        )
        self._render_items()

    def _remove_item(self) -> None:
        row = self.selected_table.currentRow()
        if 0 <= row < len(self.items):
            self.items.pop(row)
            self._render_items()

    def _render_items(self) -> None:
        self.selected_table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            values = [
                item["herb_name"],
                f"{item['dose_g']:g}",
                SPECIAL.get(item["special"], item["special"]),
            ]
            for col, value in enumerate(values):
                self.selected_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _submit(self) -> None:
        if not self.items:
            self.presc_msg.setText("请至少加入一味饮片")
            return
        payload = {
            "formula_name": self.formula.text().strip(),
            "usage": self.usage.currentData(),
            "packs": self.packs.value(),
            "decoct_service": self.service.currentData(),
            "decoction_method": self.method.text().strip() or "常规煎煮",
            "note": self.presc_note.text().strip(),
            "items": [
                {
                    "herb_id": item["herb_id"],
                    "dose_g": item["dose_g"],
                    "special": item["special"],
                }
                for item in self.items
            ],
        }
        try:
            prescription = self.api.create_tcm_prescription(
                self.encounter_id.value(), payload
            )
        except ApiError as e:
            self.presc_msg.setText(f"提交失败（{e.status_code}）：{e.detail}")
            return
        self.presc_msg.setText(
            f"已开方 {prescription['prescription_no']}，金额 {prescription['total_amount']:.2f} 元"
        )
        self.items.clear()
        self._render_items()
        self._load_my()

    def _load_my(self) -> None:
        try:
            rows = self.api.list_tcm_prescriptions()
        except ApiError as e:
            self.presc_msg.setText(f"加载处方失败（{e.status_code}）：{e.detail}")
            return
        self.my_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = [
                item["prescription_no"],
                str(item["encounter_id"]),
                item["formula_name"] or "—",
                str(item["packs"]),
                P_STATUS.get(item["status"], item["status"]),
                f"{item['total_amount']:.2f}",
            ]
            for col, value in enumerate(values):
                self.my_table.setItem(row, col, QTableWidgetItem(str(value)))

    # ---------- 中药房 ----------
    def _build_pharmacy_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        refresh = QPushButton("刷新中药处方")
        refresh.clicked.connect(self._load_pharmacy)
        layout.addWidget(refresh)
        self.rx_table = QTableWidget(0, 7)
        self.rx_table.setHorizontalHeaderLabels(
            ["处方号", "患者", "方名", "剂数", "煎药", "状态", "金额"]
        )
        self.rx_table.cellClicked.connect(self._select_rx)
        layout.addWidget(self.rx_table, 1)
        buttons = QHBoxLayout()
        review = QPushButton("审核通过")
        review.clicked.connect(self._review_rx)
        dispense = QPushButton("发药/转煎药")
        dispense.clicked.connect(self._dispense_rx)
        buttons.addWidget(review)
        buttons.addWidget(dispense)
        layout.addLayout(buttons)
        self.rx_msg = QLabel("")
        self.rx_msg.setWordWrap(True)
        layout.addWidget(self.rx_msg)
        return page

    def _load_pharmacy(self) -> None:
        try:
            rows = self.api.list_tcm_prescriptions()
        except ApiError as e:
            self.rx_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.rx_rows = rows
        self.rx_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = [
                item["prescription_no"],
                item["patient_name"],
                item["formula_name"] or "—",
                str(item["packs"]),
                "代煎" if item["decoct_service"] == "decoct" else "自煎",
                P_STATUS.get(item["status"], item["status"]),
                f"{item['total_amount']:.2f}",
            ]
            for col, value in enumerate(values):
                self.rx_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _select_rx(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.rx_rows):
            self.current_rx = self.rx_rows[row]
            self.rx_msg.setText(
                f"当前处方 {self.current_rx['prescription_no']}（"
                f"{P_STATUS.get(self.current_rx['status'], self.current_rx['status'])}）"
            )

    def _review_rx(self) -> None:
        rx = getattr(self, "current_rx", None)
        if not rx:
            self.rx_msg.setText("请先选择处方")
            return
        try:
            self.api.review_tcm(rx["id"])
        except ApiError as e:
            self.rx_msg.setText(f"审核失败（{e.status_code}）：{e.detail}")
            return
        self.rx_msg.setText("处方已审核")
        self._load_pharmacy()

    def _dispense_rx(self) -> None:
        rx = getattr(self, "current_rx", None)
        if not rx:
            self.rx_msg.setText("请先选择处方")
            return
        try:
            result = self.api.dispense_tcm(rx["id"])
        except ApiError as e:
            self.rx_msg.setText(f"发药失败（{e.status_code}）：{e.detail}")
            return
        self.rx_msg.setText(
            f"已发药，处方状态 {P_STATUS.get(result['status'], result['status'])}"
        )
        self._load_pharmacy()
        self._load_decoction()

    # ---------- 煎药室 ----------
    def _build_decoction_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        refresh = QPushButton("刷新煎药单")
        refresh.clicked.connect(self._load_decoction)
        layout.addWidget(refresh)
        self.dec_table = QTableWidget(0, 8)
        self.dec_table.setHorizontalHeaderLabels(
            ["煎药单", "患者", "处方", "状态", "浸泡", "煎煮", "袋数", "取药"]
        )
        self.dec_table.cellClicked.connect(self._select_dec)
        layout.addWidget(self.dec_table, 1)

        box = QGroupBox("煎药过程")
        form = QFormLayout(box)
        self.soak_minutes = QSpinBox()
        self.soak_minutes.setRange(0, 240)
        self.soak_minutes.setValue(30)
        self.machine = QLineEdit("煎药机-1")
        self.decoct_minutes = QSpinBox()
        self.decoct_minutes.setRange(1, 300)
        self.decoct_minutes.setValue(40)
        self.bags = QSpinBox()
        self.bags.setRange(1, 200)
        self.bags.setValue(6)
        self.bag_volume = QSpinBox()
        self.bag_volume.setRange(0, 1000)
        self.bag_volume.setValue(200)
        self.receiver = QLineEdit()
        self.receiver.setPlaceholderText("取药人")
        form.addRow("浸泡(分钟)", self.soak_minutes)
        form.addRow("煎药机", self.machine)
        form.addRow("煎煮(分钟)", self.decoct_minutes)
        form.addRow("袋数", self.bags)
        form.addRow("每袋ml", self.bag_volume)
        form.addRow("取药人", self.receiver)
        layout.addWidget(box)
        buttons = QHBoxLayout()
        soak = QPushButton("开始浸泡")
        soak.clicked.connect(self._soak)
        decoct = QPushButton("开始煎煮")
        decoct.clicked.connect(self._decoct)
        package = QPushButton("包装完成")
        package.clicked.connect(self._package)
        issue = QPushButton("发放")
        issue.clicked.connect(self._issue)
        for button in (soak, decoct, package, issue):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.dec_msg = QLabel("")
        self.dec_msg.setWordWrap(True)
        layout.addWidget(self.dec_msg)
        return page

    def _load_decoction(self) -> None:
        try:
            rows = self.api.list_decoctions()
        except ApiError as e:
            self.dec_msg.setText(f"加载煎药单失败（{e.status_code}）：{e.detail}")
            return
        self.dec_rows = rows
        self.dec_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = [
                item["order_no"],
                item["patient_name"],
                item.get("prescription_no") or "—",
                D_STATUS.get(item["status"], item["status"]),
                str(item.get("soak_minutes") or "—"),
                str(item.get("decoct_minutes") or "—"),
                str(item.get("bags") or "—"),
                item.get("receiver") or "—",
            ]
            for col, value in enumerate(values):
                self.dec_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _select_dec(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.dec_rows):
            self.current_dec = self.dec_rows[row]
            self.dec_msg.setText(
                f"当前煎药单 {self.current_dec['order_no']}（"
                f"{D_STATUS.get(self.current_dec['status'], self.current_dec['status'])}）"
            )

    def _dec_selected(self) -> dict | None:
        order = getattr(self, "current_dec", None)
        if not order:
            self.dec_msg.setText("请先选择煎药单")
        return order

    def _soak(self) -> None:
        order = self._dec_selected()
        if not order:
            return
        try:
            self.api.soak_decoction(
                order["id"], {"soak_minutes": self.soak_minutes.value()}
            )
        except ApiError as e:
            self.dec_msg.setText(f"浸泡失败（{e.status_code}）：{e.detail}")
            return
        self.dec_msg.setText("已开始浸泡")
        self._load_decoction()

    def _decoct(self) -> None:
        order = self._dec_selected()
        if not order:
            return
        try:
            self.api.decoct_decoction(
                order["id"],
                {
                    "machine_no": self.machine.text().strip(),
                    "decoct_minutes": self.decoct_minutes.value(),
                },
            )
        except ApiError as e:
            self.dec_msg.setText(f"煎煮失败（{e.status_code}）：{e.detail}")
            return
        self.dec_msg.setText("已开始煎煮")
        self._load_decoction()

    def _package(self) -> None:
        order = self._dec_selected()
        if not order:
            return
        try:
            result = self.api.package_decoction(
                order["id"],
                {
                    "bags": self.bags.value(),
                    "bag_volume_ml": self.bag_volume.value(),
                    "expires_days": 7,
                },
            )
        except ApiError as e:
            self.dec_msg.setText(f"包装失败（{e.status_code}）：{e.detail}")
            return
        self.dec_msg.setText(f"包装完成，生成 {result['bags']} 袋标签")
        self._load_decoction()

    def _issue(self) -> None:
        order = self._dec_selected()
        if not order:
            return
        receiver = self.receiver.text().strip()
        if not receiver:
            self.dec_msg.setText("请填写取药人")
            return
        try:
            self.api.issue_decoction(
                order["id"], {"pickup_method": "self", "receiver": receiver}
            )
        except ApiError as e:
            self.dec_msg.setText(f"发放失败（{e.status_code}）：{e.detail}")
            return
        self.dec_msg.setText("已发放")
        self._load_decoction()
