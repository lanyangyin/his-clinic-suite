"""药房工作站：入库单（收货/验收/入库）、发药/退药、库存查询、医保目录查询。"""
from PySide6.QtWidgets import (
    QComboBox,
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
from his_client.config import load_config
from his_client.labels import zh
from his_client.ui.payment import PaymentPanel

ORDER_TYPES = [
    ("drug", "药品"),
    ("device", "医疗器械"),
    ("consumable", "耗材"),
    ("office", "办公用品"),
    ("other", "其他/混合"),
]
STORAGE_OPTIONS = ["", "常温", "阴凉", "冷藏"]
CATALOG_CATEGORIES = [("", "全部"), ("甲", "甲类"), ("乙", "乙类"), ("丙", "丙类/自费")]


class PharmacyWidget(QWidget):
    def __init__(self, api: ApiClient, role: str = "pharmacist", parent=None):
        super().__init__(parent)
        self.api = api
        self.role = role
        self.insurance_enabled = load_config().insurance_enabled
        self.pending_items: list[dict] = []
        self.outbound_items: list[dict] = []
        self.current_order: dict | None = None
        self.handle_order: dict | None = None

        tabs = QTabWidget()
        # 库房：入库 / 出库审核 / 总库库存
        if role in ("warehouse", "admin"):
            tabs.addTab(self._build_inbound_tab(), "入库单")
            tabs.addTab(self._build_outbound_handle_tab(), "出库处理")
            tabs.addTab(self._build_warehouse_stock_tab(), "总库库存")
        # 药房：领用申请 / 发药退药 / 药房库存 / 医保目录
        if role in ("pharmacist", "admin"):
            tabs.addTab(self._build_outbound_tab(), "领用出库")
            tabs.addTab(self._build_dispense_tab(), "发药 / 退药")
            tabs.addTab(PaymentPanel(api), "收费")
            tabs.addTab(self._build_stock_tab(), "库存查询")
            if self.insurance_enabled:
                tabs.addTab(self._build_catalog_tab(), "医保目录")
        tabs.addTab(self._build_expiry_tab(), "效期预警")
        tabs.addTab(self._build_trace_tab(), "追溯码")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        if role in ("warehouse", "admin"):
            self._load_drugs()  # 入库药品下拉默认加载医保目录
            self._load_materials()  # 入库物资下拉默认加载医保耗材目录

    # ---------- 入库单 ----------
    def _build_inbound_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QGroupBox("新建入库单（收货）")
        header_form = QFormLayout(header)
        self.in_type = QComboBox()
        for value, label in ORDER_TYPES:
            self.in_type.addItem(label, value)
        self.in_supplier = QComboBox()
        self.in_supplier.addItem("无供应商", None)
        self.in_delivery = QLineEdit()
        self.in_delivery.setPlaceholderText("随货同行单号")
        self.in_invoice = QLineEdit()
        self.in_invoice.setPlaceholderText("发票号")
        row = QHBoxLayout()
        refresh = QPushButton("刷新供应商")
        refresh.clicked.connect(self._load_suppliers)
        row.addWidget(self.in_supplier)
        row.addWidget(refresh)
        header_form.addRow("类型", self.in_type)
        header_form.addRow("供应商", row)
        header_form.addRow("随货单号", self.in_delivery)
        header_form.addRow("发票号", self.in_invoice)
        layout.addWidget(header)

        items_box = QGroupBox("添加明细")
        items_layout = QVBoxLayout(items_box)

        drug_row = QHBoxLayout()
        self.in_drug_source = QComboBox()
        if self.insurance_enabled:
            self.in_drug_source.addItem("医保目录（默认）", "catalog")
        self.in_drug_source.addItem("本店药品", "local")
        self.in_drug_source.currentIndexChanged.connect(self._load_drugs)
        self.in_drug = QComboBox()
        load_drugs = QPushButton("刷新药品")
        load_drugs.clicked.connect(self._load_drugs)
        self.in_batch = QLineEdit()
        self.in_batch.setPlaceholderText("批号")
        self.in_expiry = QLineEdit()
        self.in_expiry.setPlaceholderText("效期 YYYY-MM-DD")
        self.in_qty = QSpinBox()
        self.in_qty.setRange(1, 100000)
        self.in_qty.setValue(10)
        self.in_price = QLineEdit()
        self.in_price.setPlaceholderText("单价（空=基准价）")
        self.in_storage = QComboBox()
        self.in_storage.addItems(STORAGE_OPTIONS)
        self.in_location = QLineEdit()
        self.in_location.setPlaceholderText("货位")
        add_drug = QPushButton("添加药品行")
        add_drug.clicked.connect(self._add_drug_item)
        for w in (self.in_drug_source, self.in_drug, load_drugs, self.in_batch, self.in_expiry, self.in_qty, self.in_price, self.in_storage, self.in_location, add_drug):
            drug_row.addWidget(w)
        items_layout.addWidget(QLabel("药品行：来源 / 药品 / 批号 / 效期 / 数量 / 单价 / 储存 / 货位"))
        items_layout.addLayout(drug_row)

        insurance_row = QHBoxLayout()
        self.in_insurance_code = QLineEdit()
        self.in_insurance_code.setPlaceholderText("医保编码（可空，空则取目录）")
        self.in_insurance_name = QLineEdit()
        self.in_insurance_name.setPlaceholderText("医保名称（可空）")
        self.in_insurance_category = QComboBox()
        for value in ("未对码", "甲", "乙", "丙", "自费"):
            self.in_insurance_category.addItem(value, value)
        insurance_row.addWidget(self.in_insurance_code)
        insurance_row.addWidget(self.in_insurance_name)
        insurance_row.addWidget(self.in_insurance_category)
        items_layout.addWidget(QLabel("医保属性（快照）：编码 / 名称 / 甲乙丙类别"))
        items_layout.addLayout(insurance_row)

        material_row = QHBoxLayout()
        self.in_material_source = QComboBox()
        if self.insurance_enabled:
            self.in_material_source.addItem("医保耗材目录（默认）", "catalog")
        self.in_material_source.addItem("本店物资", "local")
        self.in_material_source.currentIndexChanged.connect(self._load_materials)
        self.in_material = QComboBox()
        load_materials = QPushButton("刷新物资")
        load_materials.clicked.connect(self._load_materials)
        self.in_m_qty = QSpinBox()
        self.in_m_qty.setRange(1, 100000)
        self.in_m_qty.setValue(1)
        self.in_m_price = QLineEdit()
        self.in_m_price.setPlaceholderText("单价（空=目录价）")
        self.in_warehouse = QLineEdit()
        self.in_warehouse.setText("总库")
        add_material = QPushButton("添加物资行")
        add_material.clicked.connect(self._add_material_item)
        for w in (self.in_material_source, self.in_material, load_materials, self.in_m_qty, self.in_m_price, self.in_warehouse, add_material):
            material_row.addWidget(w)
        items_layout.addWidget(QLabel("物资行：来源 / 器械/耗材/办公 / 数量 / 单价 / 库房"))
        items_layout.addLayout(material_row)

        self.pending_table = QTableWidget(0, 8)
        self.pending_table.setHorizontalHeaderLabels(
            ["类型", "名称", "批号", "数量", "单价", "金额", "医保编码", "医保类别"]
        )
        items_layout.addWidget(self.pending_table)

        actions = QHBoxLayout()
        clear = QPushButton("清空明细")
        clear.clicked.connect(self._clear_items)
        submit = QPushButton("提交入库单")
        submit.clicked.connect(self._submit_order)
        actions.addWidget(clear)
        actions.addWidget(submit)
        actions.addStretch(1)
        items_layout.addLayout(actions)
        self.in_msg = QLabel("")
        self.in_msg.setWordWrap(True)
        items_layout.addWidget(self.in_msg)
        layout.addWidget(items_box)

        handle_box = QGroupBox("入库单处理（验收 / 入库 / 取消）")
        handle_layout = QVBoxLayout(handle_box)
        filter_row = QHBoxLayout()
        self.order_status_filter = QComboBox()
        for value, label in [("", "全部"), ("received", "已收货"), ("checked", "已验收"), ("stocked", "已入库"), ("cancelled", "已取消")]:
            self.order_status_filter.addItem(label, value)
        refresh_orders = QPushButton("刷新入库单")
        refresh_orders.clicked.connect(self._load_orders)
        filter_row.addWidget(QLabel("状态"))
        filter_row.addWidget(self.order_status_filter)
        filter_row.addWidget(refresh_orders)
        filter_row.addStretch(1)
        handle_layout.addLayout(filter_row)

        self.order_table = QTableWidget(0, 5)
        self.order_table.setHorizontalHeaderLabels(
            ["单号", "类型", "状态", "供应商", "明细数"]
        )
        handle_layout.addWidget(self.order_table)

        self.order_items_table = QTableWidget(0, 6)
        self.order_items_table.setHorizontalHeaderLabels(
            ["明细ID", "名称", "批号", "数量", "不合格", "单价"]
        )
        handle_layout.addWidget(self.order_items_table)

        check_row = QHBoxLayout()
        self.reject_qty = QSpinBox()
        self.reject_qty.setRange(0, 100000)
        self.reject_reason = QLineEdit()
        self.reject_reason.setPlaceholderText("不合格原因（选中明细后填写）")
        check_all = QPushButton("全部合格验收")
        check_all.clicked.connect(self._check_all)
        check_partial = QPushButton("提交不合格验收")
        check_partial.clicked.connect(self._check_selected)
        stock = QPushButton("入库")
        stock.clicked.connect(self._stock_order)
        cancel = QPushButton("取消入库单")
        cancel.clicked.connect(self._cancel_order)
        for w in (self.reject_qty, self.reject_reason, check_all, check_partial, stock, cancel):
            check_row.addWidget(w)
        handle_layout.addLayout(check_row)

        self.order_msg = QLabel("")
        self.order_msg.setWordWrap(True)
        handle_layout.addWidget(self.order_msg)
        layout.addWidget(handle_box)
        layout.addStretch(1)
        return page

    def _load_suppliers(self) -> None:
        try:
            suppliers = self.api.list_suppliers()
        except ApiError as e:
            self.in_msg.setText(f"加载供应商失败：{e.detail}")
            return
        self.in_supplier.clear()
        self.in_supplier.addItem("无供应商", None)
        for supplier in suppliers:
            self.in_supplier.addItem(supplier["name"], supplier["id"])

    def _load_drugs(self) -> None:
        source = (
            self.in_drug_source.currentData()
            if hasattr(self, "in_drug_source")
            else "local"
        )
        self.in_drug.clear()
        if source == "catalog":
            try:
                rows = self.api.search_insurance_catalog(limit=500)
            except ApiError as e:
                self.in_msg.setText(f"加载医保目录失败：{e.detail}")
                return
            if rows:
                for row in rows:
                    category = row.get("category") or "—"
                    spec = row.get("spec") or ""
                    self.in_drug.addItem(
                        f"{row['name']} {spec}【{category}类】",
                        row["national_code"],
                    )
                self.in_msg.setText(
                    f"医保目录 {len(rows)} 条（默认来源，选中后自动落地为本店药品）"
                )
                return
            self.in_msg.setText(
                "医保目录为空：请先在管理台上传/同步目录；已切换为本店药品"
            )
            self.in_drug_source.setCurrentIndex(1)
            return

        try:
            drugs = self.api.list_drugs()
        except ApiError as e:
            self.in_msg.setText(f"加载药品失败：{e.detail}")
            return
        self.in_drug.clear()
        for drug in drugs:
            self.in_drug.addItem(f"{drug['name']}（{drug['base_price']:.2f}）", drug["id"])
        self.in_msg.setText(f"本店药品 {len(drugs)} 条")

    def _load_materials(self) -> None:
        source = (
            self.in_material_source.currentData()
            if hasattr(self, "in_material_source")
            else "local"
        )
        self.in_material.clear()
        if source == "catalog":
            try:
                rows = self.api.search_insurance_materials(limit=500)
            except ApiError as e:
                self.in_msg.setText(f"加载耗材目录失败：{e.detail}")
                return
            if rows:
                for row in rows:
                    category = row.get("category") or row.get("material_type") or "—"
                    spec = row.get("spec") or row.get("model") or ""
                    self.in_material.addItem(
                        f"{row['name']} {spec}【{category}】", row["code"]
                    )
                self.in_msg.setText(
                    f"医保耗材目录 {len(rows)} 条（默认来源，选中后自动落地为本店物资）"
                )
                return
            self.in_msg.setText(
                "医保耗材目录为空：请先在管理台上传目录；已切换为本店物资"
            )
            self.in_material_source.setCurrentIndex(1)
            return

        try:
            items = self.api.list_material_items()
        except ApiError as e:
            self.in_msg.setText(f"加载物资失败：{e.detail}")
            return
        self.in_material.clear()
        for item in items:
            self.in_material.addItem(
                f"{item['name']}（{item.get('category')}）", item["id"]
            )
        self.in_msg.setText(f"本店物资 {len(items)} 条")

    def _add_drug_item(self) -> None:
        source = (
            self.in_drug_source.currentData()
            if hasattr(self, "in_drug_source")
            else "local"
        )
        selected = self.in_drug.currentData()
        if not selected:
            self.in_msg.setText("请先刷新并选择药品")
            return
        drug_id = selected
        if source == "catalog":
            try:
                drug = self.api.ensure_drug_from_catalog(str(selected))
            except ApiError as e:
                self.in_msg.setText(f"医保目录药品落地失败（{e.status_code}）：{e.detail}")
                return
            drug_id = drug["id"]
            if not self.in_price.text().strip() and drug.get("base_price"):
                self.in_price.setText(f"{drug['base_price']:.2f}")
        price = self.in_price.text().strip()
        expiry = self.in_expiry.text().strip()
        if not expiry:
            self.in_msg.setText("药品行必须填写有效期（YYYY-MM-DD）")
            return
        item = {
            "kind": "drug",
            "drug_id": drug_id,
            "batch_no": self.in_batch.text().strip(),
            "expiry": expiry,
            "quantity": self.in_qty.value(),
            "unit_price": float(price) if price else 0,
            "storage_condition": self.in_storage.currentText(),
            "location": self.in_location.text().strip(),
            "insurance_code": self.in_insurance_code.text().strip(),
            "insurance_name": self.in_insurance_name.text().strip(),
            "insurance_category": self.in_insurance_category.currentData(),
        }
        self.pending_items.append(item)
        self._refresh_pending()
        self.in_msg.setText("已添加药品行，可继续添加或提交")

    def _add_material_item(self) -> None:
        source = (
            self.in_material_source.currentData()
            if hasattr(self, "in_material_source")
            else "local"
        )
        selected = self.in_material.currentData()
        if not selected:
            self.in_msg.setText("请先刷新并选择物资")
            return
        material_id = selected
        if source == "catalog":
            try:
                item = self.api.ensure_material_from_catalog(str(selected))
            except ApiError as e:
                self.in_msg.setText(f"医保耗材落地失败（{e.status_code}）：{e.detail}")
                return
            material_id = item["id"]
            if not self.in_m_price.text().strip() and item.get("price"):
                self.in_m_price.setText(f"{item['price']:.2f}")
        price = self.in_m_price.text().strip()
        item = {
            "kind": "material",
            "material_id": material_id,
            "quantity": self.in_m_qty.value(),
            "unit_price": float(price) if price else 0,
            "warehouse": self.in_warehouse.text().strip() or "总库",
            "insurance_code": self.in_insurance_code.text().strip(),
            "insurance_name": self.in_insurance_name.text().strip(),
            "insurance_category": self.in_insurance_category.currentData(),
        }
        self.pending_items.append(item)
        self._refresh_pending()
        self.in_msg.setText("已添加物资行，可继续添加或提交")

    def _refresh_pending(self) -> None:
        self.pending_table.setRowCount(len(self.pending_items))
        for row, item in enumerate(self.pending_items):
            name = (
                self.in_drug.itemText(self.in_drug.findData(item.get("drug_id")))
                if item["kind"] == "drug"
                else self.in_material.itemText(self.in_material.findData(item.get("material_id")))
            )
            kind = "药品" if item["kind"] == "drug" else "物资"
            amount = item["quantity"] * item["unit_price"]
            values = [
                kind,
                name,
                item.get("batch_no", ""),
                str(item["quantity"]),
                f"{item['unit_price']:.2f}",
                f"{amount:.2f}",
                item.get("insurance_code", ""),
                item.get("insurance_category", "未对码"),
            ]
            for col, value in enumerate(values):
                self.pending_table.setItem(row, col, QTableWidgetItem(value))

    def _clear_items(self) -> None:
        self.pending_items = []
        self._refresh_pending()

    def _submit_order(self) -> None:
        if not self.pending_items:
            self.in_msg.setText("请先添加至少一行明细")
            return
        payload = {
            "order_type": self.in_type.currentData(),
            "supplier_id": self.in_supplier.currentData(),
            "delivery_no": self.in_delivery.text().strip(),
            "invoice_no": self.in_invoice.text().strip(),
            "items": self.pending_items,
        }
        try:
            order = self.api.create_inbound_order(payload)
        except ApiError as e:
            self.in_msg.setText(f"提交失败（{e.status_code}）：{e.detail}")
            return
        self.in_msg.setText(
            f"入库单已创建：{order['order_no']}（{zh('inbound_status', order['status'])}），等待验收"
        )
        self._clear_items()
        self._load_orders()

    def _load_orders(self) -> None:
        try:
            orders = self.api.list_inbound_orders(
                status=self.order_status_filter.currentData() or None
            )
        except ApiError as e:
            self.order_msg.setText(f"加载入库单失败：{e.detail}")
            return
        self.order_table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            values = [
                order["order_no"],
                dict(ORDER_TYPES).get(order["order_type"], order["order_type"]),
                zh("inbound_status", order["status"]),
                str(order.get("supplier_id") or "—"),
                str(len(order.get("items") or [])),
            ]
            for col, value in enumerate(values):
                self.order_table.setItem(row, col, QTableWidgetItem(value))
        self.order_table.cellClicked.connect(self._select_order)
        self.order_msg.setText(f"共 {len(orders)} 张入库单")

    def _select_order(self, row: int, _col: int) -> None:
        order_no = self.order_table.item(row, 0).text()
        try:
            orders = self.api.list_inbound_orders()
        except ApiError as e:
            self.order_msg.setText(f"加载失败：{e.detail}")
            return
        order = next((o for o in orders if o["order_no"] == order_no), None)
        if not order:
            return
        self.current_order = order
        items = order.get("items") or []
        self.order_items_table.setRowCount(len(items))
        for index, item in enumerate(items):
            values = [
                str(item["id"]),
                item["name"],
                item.get("batch_no", ""),
                str(item["quantity"]),
                str(item.get("rejected_qty", 0)),
                f"{item['unit_price']:.2f}",
            ]
            for col, value in enumerate(values):
                self.order_items_table.setItem(index, col, QTableWidgetItem(value))
        self.order_msg.setText(
            f"当前入库单 {order['order_no']}（{zh('inbound_status', order['status'])}），明细 {len(items)} 行"
        )

    def _check_all(self) -> None:
        if not self.current_order:
            self.order_msg.setText("请先在列表中选择入库单")
            return
        try:
            order = self.api.check_inbound_order(self.current_order["id"], [])
        except ApiError as e:
            self.order_msg.setText(f"验收失败（{e.status_code}）：{e.detail}")
            return
        self.order_msg.setText(f"已全部合格验收：{order['order_no']}")
        self._load_orders()

    def _check_selected(self) -> None:
        if not self.current_order:
            self.order_msg.setText("请先选择入库单")
            return
        row = self.order_items_table.currentRow()
        if row < 0:
            self.order_msg.setText("请在明细中选中一行")
            return
        item_id = int(self.order_items_table.item(row, 0).text())
        try:
            order = self.api.check_inbound_order(
                self.current_order["id"],
                [
                    {
                        "item_id": item_id,
                        "rejected_qty": self.reject_qty.value(),
                        "reject_reason": self.reject_reason.text().strip(),
                    }
                ],
            )
        except ApiError as e:
            self.order_msg.setText(f"验收失败（{e.status_code}）：{e.detail}")
            return
        self.order_msg.setText(f"验收完成：{order['order_no']}")
        self._load_orders()

    def _stock_order(self) -> None:
        if not self.current_order:
            self.order_msg.setText("请先选择入库单")
            return
        try:
            order = self.api.stock_inbound_order(self.current_order["id"])
        except ApiError as e:
            self.order_msg.setText(f"入库失败（{e.status_code}）：{e.detail}")
            return
        self.order_msg.setText(f"入库成功：{order['order_no']}")
        self._load_orders()

    def _cancel_order(self) -> None:
        if not self.current_order:
            self.order_msg.setText("请先选择入库单")
            return
        try:
            order = self.api.cancel_inbound_order(self.current_order["id"])
        except ApiError as e:
            self.order_msg.setText(f"取消失败（{e.status_code}）：{e.detail}")
            return
        self.order_msg.setText(f"已取消：{order['order_no']}")
        self._load_orders()

    # ---------- 发药 / 退药 ----------
    def _build_dispense_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("门诊发药")
        row = QHBoxLayout(box)
        self.disp_encounter_id = QSpinBox()
        self.disp_encounter_id.setRange(1, 10_000_000)
        self.disp_window = QLineEdit("1号窗")
        self.disp_window.setMaximumWidth(90)
        self.disp_note = QLineEdit()
        self.disp_note.setPlaceholderText("核对备注")
        submit = QPushButton("核对发药")
        submit.clicked.connect(self._dispense)
        call_btn = QPushButton("叫号")
        call_btn.clicked.connect(self._call)
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.disp_encounter_id)
        row.addWidget(QLabel("窗口"))
        row.addWidget(self.disp_window)
        row.addWidget(self.disp_note)
        row.addWidget(call_btn)
        row.addWidget(submit)
        layout.addWidget(box)

        list_row = QHBoxLayout()
        refresh = QPushButton("刷新待发药队列")
        refresh.clicked.connect(self._load_worklist)
        list_row.addWidget(refresh)
        list_row.addStretch(1)
        layout.addLayout(list_row)
        self.worklist_table = QTableWidget(0, 7)
        self.worklist_table.setHorizontalHeaderLabels(
            ["叫号", "取药码", "患者", "处方数", "药品", "状态", "窗口"]
        )
        self.worklist_table.cellClicked.connect(self._select_worklist)
        layout.addWidget(self.worklist_table, 1)

        sign_row = QHBoxLayout()
        self.pickup_code = QLineEdit()
        self.pickup_code.setPlaceholderText("扫取药码/输入")
        verify_btn = QPushButton("核对取药码")
        verify_btn.clicked.connect(self._verify_code)
        self.receiver_name = QLineEdit()
        self.receiver_name.setPlaceholderText("取药人")
        self.receiver_relation = QLineEdit("本人")
        self.signature_path = QLineEdit()
        self.signature_path.setPlaceholderText("签名图片路径（可选）")
        sign_btn = QPushButton("选择签名")
        sign_btn.clicked.connect(self._pick_signature)
        sign_row.addWidget(self.pickup_code)
        sign_row.addWidget(verify_btn)
        sign_row.addWidget(self.receiver_name)
        sign_row.addWidget(self.receiver_relation)
        sign_row.addWidget(self.signature_path)
        sign_row.addWidget(sign_btn)
        layout.addLayout(sign_row)

        self.disp_msg = QLabel("")
        self.disp_msg.setWordWrap(True)
        layout.addWidget(self.disp_msg)

        return_box = QGroupBox("退药")
        return_row = QHBoxLayout(return_box)
        self.return_dispense_id = QSpinBox()
        self.return_dispense_id.setRange(1, 10_000_000)
        return_btn = QPushButton("退药（库存回补）")
        return_btn.clicked.connect(self._return_dispense)
        return_row.addWidget(QLabel("发药记录 ID"))
        return_row.addWidget(self.return_dispense_id)
        return_row.addWidget(return_btn)
        layout.addWidget(return_box)

        self.return_msg = QLabel("")
        self.return_msg.setWordWrap(True)
        layout.addWidget(self.return_msg)
        layout.addStretch(1)
        self._load_worklist()
        return page

    def _dispense(self) -> None:
        try:
            record = self.api.dispense(
                self.disp_encounter_id.value(),
                self.disp_note.text().strip(),
                self.pickup_code.text().strip(),
                self.receiver_name.text().strip(),
                self.receiver_relation.text().strip() or "本人",
            )
        except ApiError as e:
            self.disp_msg.setText(f"发药失败（{e.status_code}）：{e.detail}")
            return
        if self.signature_path.text().strip():
            try:
                self.api.upload_dispense_signature(
                    record["id"], self.signature_path.text().strip()
                )
            except (ApiError, OSError) as e:
                self.disp_msg.setText(f"已发药，但签名上传失败：{e}")
                self.return_dispense_id.setValue(record["id"])
                self._load_worklist()
                return
        self.disp_msg.setText(
            f"核对发药成功：记录 {record['id']}，取药人 {record['receiver_name'] or '—'}"
        )
        self.return_dispense_id.setValue(record["id"])
        self._load_worklist()

    def _load_worklist(self) -> None:
        try:
            self.worklist = self.api.pharmacy_worklist()
        except ApiError as e:
            self.disp_msg.setText(f"队列加载失败（{e.status_code}）：{e.detail}")
            return
        self.worklist_table.setRowCount(len(self.worklist))
        for row, item in enumerate(self.worklist):
            values = [
                item["queue_no"] or "—",
                item.get("pickup_code", ""),
                item["patient_name"],
                item["item_count"],
                item["drugs"],
                {"waiting": "待叫号", "called": "已叫号"}.get(
                    item["call_status"], item["call_status"]
                ),
                item["window_no"] or "—",
            ]
            for col, value in enumerate(values):
                self.worklist_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.disp_msg.setText(f"待发药 {len(self.worklist)} 人")

    def _verify_code(self) -> None:
        code = self.pickup_code.text().strip()
        if not code:
            self.disp_msg.setText("请扫描或输入取药码")
            return
        try:
            row = self.api.verify_pickup_code(code)
        except ApiError as e:
            self.disp_msg.setText(f"取药码核对失败（{e.status_code}）：{e.detail}")
            return
        self.disp_encounter_id.setValue(row["encounter_id"])
        self.disp_msg.setText(f"取药码核对通过：{row['patient_name']}")

    def _pick_signature(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择签名图片", "", "图片 (*.png *.jpg *.jpeg)"
        )
        if path:
            self.signature_path.setText(path)

    def _select_worklist(self, row: int, _col: int) -> None:
        if 0 <= row < len(getattr(self, "worklist", [])):
            item = self.worklist[row]
            self.disp_encounter_id.setValue(item["encounter_id"])
            self.pickup_code.setText(item.get("pickup_code", ""))

    def _call(self) -> None:
        try:
            call = self.api.call_pharmacy(
                self.disp_encounter_id.value(),
                self.disp_window.text().strip() or "1号窗",
                self.disp_note.text().strip(),
            )
        except ApiError as e:
            self.disp_msg.setText(f"叫号失败（{e.status_code}）：{e.detail}")
            return
        self.disp_msg.setText(
            f"已叫号 {call['queue_no']}，窗口 {call['window_no']}"
        )
        self._load_worklist()

    def _return_dispense(self) -> None:
        try:
            record = self.api.return_dispense(self.return_dispense_id.value())
        except ApiError as e:
            self.return_msg.setText(f"退药失败（{e.status_code}）：{e.detail}")
            return
        self.return_msg.setText(
            f"退药成功：记录 {record['id']}（{zh('dispense_status', record['status'])}），库存已回补"
        )

    # ---------- 领用出库（向库房申请） ----------
    def _build_outbound_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form_box = QGroupBox("向库房申请（审核/出库由库房操作）")
        form = QFormLayout(form_box)
        self.out_type = QComboBox()
        self.out_type.addItem("领用出库", "requisition")
        self.out_type.addItem("退库", "return")
        self.out_target_type = QComboBox()
        self.out_target_type.addItem("药房", "pharmacy")
        self.out_target_type.addItem("科室", "department")
        self.out_target_name = QLineEdit("药房")
        self.out_note = QLineEdit()
        form.addRow("类型", self.out_type)
        form.addRow("目标类型", self.out_target_type)
        form.addRow("目标名称", self.out_target_name)
        form.addRow("备注", self.out_note)

        drug_row = QHBoxLayout()
        self.out_drug = QComboBox()
        load_drug = QPushButton("刷新药品")
        load_drug.clicked.connect(self._load_outbound_drugs)
        self.out_batch = QLineEdit()
        self.out_batch.setPlaceholderText("批号")
        self.out_qty = QSpinBox()
        self.out_qty.setRange(1, 100000)
        add_drug = QPushButton("添加药品行")
        add_drug.clicked.connect(self._add_outbound_drug)
        for widget in (self.out_drug, load_drug, self.out_batch, self.out_qty, add_drug):
            drug_row.addWidget(widget)
        form.addRow("药品行", drug_row)

        material_row = QHBoxLayout()
        self.out_material = QComboBox()
        load_material = QPushButton("刷新物资")
        load_material.clicked.connect(self._load_outbound_materials)
        self.out_m_qty = QSpinBox()
        self.out_m_qty.setRange(1, 100000)
        add_material = QPushButton("添加物资行")
        add_material.clicked.connect(self._add_outbound_material)
        for widget in (self.out_material, load_material, self.out_m_qty, add_material):
            material_row.addWidget(widget)
        form.addRow("物资行", material_row)

        self.out_pending = QTableWidget(0, 4)
        self.out_pending.setHorizontalHeaderLabels(["类型", "名称", "批号", "数量"])
        form.addRow("明细", self.out_pending)

        buttons = QHBoxLayout()
        clear = QPushButton("清空明细")
        clear.clicked.connect(self._clear_outbound_items)
        submit = QPushButton("提交领用申请")
        submit.clicked.connect(self._submit_outbound)
        buttons.addWidget(clear)
        buttons.addWidget(submit)
        buttons.addStretch(1)
        form.addRow("", buttons)
        self.out_msg = QLabel("")
        self.out_msg.setWordWrap(True)
        form.addRow("", self.out_msg)
        layout.addWidget(form_box)

        list_box = QGroupBox("我的出库单")
        list_layout = QVBoxLayout(list_box)
        row = QHBoxLayout()
        self.out_status_filter = QComboBox()
        for value, label in [("", "全部"), ("submitted", "已申请"), ("approved", "已审核"), ("issued", "已出库"), ("cancelled", "已取消")]:
            self.out_status_filter.addItem(label, value)
        refresh = QPushButton("刷新出库单")
        refresh.clicked.connect(self._load_outbounds)
        row.addWidget(QLabel("状态"))
        row.addWidget(self.out_status_filter)
        row.addWidget(refresh)
        row.addStretch(1)
        list_layout.addLayout(row)

        self.outbound_table = QTableWidget(0, 4)
        self.outbound_table.setHorizontalHeaderLabels(["单号", "目标", "状态", "明细数"])
        list_layout.addWidget(self.outbound_table)
        self.outbound_items_table = QTableWidget(0, 5)
        self.outbound_items_table.setHorizontalHeaderLabels(
            ["名称", "批号", "数量", "单价", "金额"]
        )
        list_layout.addWidget(self.outbound_items_table)
        self.out_list_msg = QLabel("")
        self.out_list_msg.setWordWrap(True)
        list_layout.addWidget(self.out_list_msg)
        layout.addWidget(list_box)
        layout.addStretch(1)
        return page

    def _load_outbound_drugs(self) -> None:
        try:
            drugs = self.api.list_drugs()
        except ApiError as e:
            self.out_msg.setText(f"加载药品失败：{e.detail}")
            return
        self.out_drug.clear()
        for drug in drugs:
            self.out_drug.addItem(drug["name"], drug["id"])

    def _load_outbound_materials(self) -> None:
        try:
            items = self.api.list_material_items()
        except ApiError as e:
            self.out_msg.setText(f"加载物资失败：{e.detail}")
            return
        self.out_material.clear()
        for item in items:
            self.out_material.addItem(f"{item['name']}（{item.get('category')}）", item["id"])

    def _add_outbound_drug(self) -> None:
        drug_id = self.out_drug.currentData()
        if not drug_id:
            self.out_msg.setText("请先刷新并选择药品")
            return
        batch = self.out_batch.text().strip()
        if not batch:
            self.out_msg.setText("药品行必须填写批号")
            return
        self.outbound_items.append(
            {
                "kind": "drug",
                "drug_id": drug_id,
                "batch_no": batch,
                "quantity": self.out_qty.value(),
            }
        )
        self._refresh_outbound_pending()

    def _add_outbound_material(self) -> None:
        material_id = self.out_material.currentData()
        if not material_id:
            self.out_msg.setText("请先刷新并选择物资")
            return
        self.outbound_items.append(
            {
                "kind": "material",
                "material_id": material_id,
                "quantity": self.out_m_qty.value(),
            }
        )
        self._refresh_outbound_pending()

    def _refresh_outbound_pending(self) -> None:
        self.out_pending.setRowCount(len(self.outbound_items))
        for row, item in enumerate(self.outbound_items):
            if item["kind"] == "drug":
                name = self.out_drug.itemText(self.out_drug.findData(item["drug_id"]))
                kind = "药品"
            else:
                name = self.out_material.itemText(
                    self.out_material.findData(item["material_id"])
                )
                kind = "物资"
            values = [kind, name, item.get("batch_no", ""), str(item["quantity"])]
            for col, value in enumerate(values):
                self.out_pending.setItem(row, col, QTableWidgetItem(value))

    def _clear_outbound_items(self) -> None:
        self.outbound_items = []
        self._refresh_outbound_pending()

    def _submit_outbound(self) -> None:
        if not self.outbound_items:
            self.out_msg.setText("请先添加至少一行明细")
            return
        payload = {
            "outbound_type": self.out_type.currentData(),
            "target_type": self.out_target_type.currentData(),
            "target_name": self.out_target_name.text().strip() or "药房",
            "note": self.out_note.text().strip(),
            "items": self.outbound_items,
        }
        try:
            order = self.api.create_outbound_order(payload)
        except ApiError as e:
            self.out_msg.setText(f"提交失败（{e.status_code}）：{e.detail}")
            return
        self.out_msg.setText(
            f"领用申请已提交：{order['outbound_no']}（{zh('outbound_status', order['status'])}），等待库房审核"
        )
        self._clear_outbound_items()
        self._load_outbounds()

    def _load_outbounds(self) -> None:
        try:
            orders = self.api.list_outbound_orders(
                status=self.out_status_filter.currentData() or None
            )
        except ApiError as e:
            self.out_list_msg.setText(f"加载出库单失败：{e.detail}")
            return
        self.outbound_table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            values = [
                order["outbound_no"],
                order["target_name"],
                zh("outbound_status", order["status"]),
                str(len(order.get("items") or [])),
            ]
            for col, value in enumerate(values):
                self.outbound_table.setItem(row, col, QTableWidgetItem(value))
        self.outbound_table.cellClicked.connect(self._select_outbound)
        self.out_list_msg.setText(f"共 {len(orders)} 张出库单")

    def _select_outbound(self, row: int, _col: int) -> None:
        order_no = self.outbound_table.item(row, 0).text()
        try:
            orders = self.api.list_outbound_orders()
        except ApiError:
            return
        order = next((o for o in orders if o["outbound_no"] == order_no), None)
        if not order:
            return
        items = order.get("items") or []
        self.outbound_items_table.setRowCount(len(items))
        for index, item in enumerate(items):
            values = [
                item["name"],
                item.get("batch_no", ""),
                str(item["quantity"]),
                f"{item['unit_price']:.2f}",
                f"{item['amount']:.2f}",
            ]
            for col, value in enumerate(values):
                self.outbound_items_table.setItem(index, col, QTableWidgetItem(value))
        self.out_list_msg.setText(f"出库单 {order['outbound_no']}（{zh('outbound_status', order['status'])}）")

    # ---------- 出库处理（库房审核/出库） ----------
    def _build_outbound_handle_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        self.handle_status_filter = QComboBox()
        for value, label in [("", "全部"), ("submitted", "已申请"), ("approved", "已审核"), ("issued", "已出库"), ("cancelled", "已取消")]:
            self.handle_status_filter.addItem(label, value)
        refresh = QPushButton("刷新出库单")
        refresh.clicked.connect(self._load_handle_orders)
        row.addWidget(QLabel("状态"))
        row.addWidget(self.handle_status_filter)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)

        self.handle_table = QTableWidget(0, 4)
        self.handle_table.setHorizontalHeaderLabels(["单号", "目标", "状态", "明细数"])
        layout.addWidget(self.handle_table)

        self.handle_items_table = QTableWidget(0, 4)
        self.handle_items_table.setHorizontalHeaderLabels(["名称", "批号", "数量", "金额"])
        layout.addWidget(self.handle_items_table)

        buttons = QHBoxLayout()
        self.partial_qty = QSpinBox()
        self.partial_qty.setRange(1, 100000)
        partial = QPushButton("部分出库（选中明细）")
        partial.clicked.connect(self._issue_partial)
        approve = QPushButton("审核通过")
        approve.clicked.connect(self._approve_handle)
        issue = QPushButton("全部出库")
        issue.clicked.connect(self._issue_handle)
        cancel = QPushButton("取消出库单")
        cancel.clicked.connect(self._cancel_handle)
        purchase = QPushButton("缺货生成采购申请")
        purchase.clicked.connect(self._create_purchase_request)
        buttons.addWidget(self.partial_qty)
        buttons.addWidget(partial)
        buttons.addWidget(approve)
        buttons.addWidget(issue)
        buttons.addWidget(cancel)
        buttons.addWidget(purchase)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.handle_msg = QLabel("")
        self.handle_msg.setWordWrap(True)
        layout.addWidget(self.handle_msg)
        layout.addStretch(1)
        return page

    def _load_handle_orders(self) -> None:
        try:
            orders = self.api.list_outbound_orders(
                status=self.handle_status_filter.currentData() or None
            )
        except ApiError as e:
            self.handle_msg.setText(f"加载出库单失败：{e.detail}")
            return
        self.handle_table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            values = [
                order["outbound_no"],
                order["target_name"],
                zh("outbound_status", order["status"]),
                str(len(order.get("items") or [])),
            ]
            for col, value in enumerate(values):
                self.handle_table.setItem(row, col, QTableWidgetItem(value))
        self.handle_table.cellClicked.connect(self._select_handle_order)
        self.handle_msg.setText(f"共 {len(orders)} 张出库单")

    def _select_handle_order(self, row: int, _col: int) -> None:
        order_no = self.handle_table.item(row, 0).text()
        try:
            orders = self.api.list_outbound_orders()
        except ApiError:
            return
        order = next((o for o in orders if o["outbound_no"] == order_no), None)
        if not order:
            return
        self.handle_order = order
        items = order.get("items") or []
        self.handle_items_table.setRowCount(len(items))
        for index, item in enumerate(items):
            values = [
                item["name"],
                item.get("batch_no", ""),
                str(item["quantity"]),
                f"{item['amount']:.2f}",
            ]
            for col, value in enumerate(values):
                self.handle_items_table.setItem(index, col, QTableWidgetItem(value))
        self.handle_msg.setText(f"出库单 {order['outbound_no']}（{zh('outbound_status', order['status'])}）")

    def _approve_handle(self) -> None:
        if not self.handle_order:
            self.handle_msg.setText("请先选择出库单")
            return
        try:
            order = self.api.approve_outbound_order(self.handle_order["id"])
        except ApiError as e:
            self.handle_msg.setText(f"审核失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText(f"已审核：{order['outbound_no']}")
        self._load_handle_orders()

    def _issue_handle(self) -> None:
        if not self.handle_order:
            self.handle_msg.setText("请先选择出库单")
            return
        try:
            order = self.api.issue_outbound_order(self.handle_order["id"])
        except ApiError as e:
            self.handle_msg.setText(f"出库失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText(f"出库完成：{order['outbound_no']}（{zh('outbound_status', order['status'])}）")
        self._load_handle_orders()

    def _issue_partial(self) -> None:
        if not self.handle_order:
            self.handle_msg.setText("请先选择出库单")
            return
        row = self.handle_items_table.currentRow()
        if row < 0:
            self.handle_msg.setText("请在明细中选中一行")
            return
        item_id = None
        for item in self.handle_order.get("items") or []:
            if item["name"] == self.handle_items_table.item(row, 0).text():
                item_id = item["id"]
                break
        if item_id is None:
            self.handle_msg.setText("无法识别选中明细")
            return
        try:
            order = self.api.issue_outbound_order(
                self.handle_order["id"],
                items=[{"item_id": item_id, "quantity": self.partial_qty.value()}],
            )
        except ApiError as e:
            self.handle_msg.setText(f"部分出库失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText(
            f"部分出库完成：{order['outbound_no']}（{zh('outbound_status', order['status'])}）"
        )
        self._load_handle_orders()

    def _cancel_handle(self) -> None:
        if not self.handle_order:
            self.handle_msg.setText("请先选择出库单")
            return
        try:
            order = self.api.cancel_outbound_order(self.handle_order["id"])
        except ApiError as e:
            self.handle_msg.setText(f"取消失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText(f"已取消：{order['outbound_no']}")
        self._load_handle_orders()

    # ---------- 总库库存 ----------
    def _build_warehouse_stock_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        refresh = QPushButton("刷新总库库存")
        refresh.clicked.connect(self._load_warehouse_stocks)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)

        self.wh_drug_table = QTableWidget(0, 5)
        self.wh_drug_table.setHorizontalHeaderLabels(["药品ID", "批次", "效期", "数量", "药品"])
        layout.addWidget(self.wh_drug_table)
        self.wh_material_table = QTableWidget(0, 4)
        self.wh_material_table.setHorizontalHeaderLabels(["物资ID", "名称", "库房", "数量"])
        layout.addWidget(self.wh_material_table)

        self.wh_msg = QLabel("")
        self.wh_msg.setWordWrap(True)
        layout.addWidget(self.wh_msg)
        return page

    def _load_warehouse_stocks(self) -> None:
        try:
            drugs = self.api.list_warehouse_stocks()
            materials = [
                row for row in self.api.list_material_stocks() if row["warehouse"] == "总库"
            ]
        except ApiError as e:
            self.wh_msg.setText(f"加载总库库存失败：{e.detail}")
            return
        self.wh_drug_table.setRowCount(len(drugs))
        for row, stock in enumerate(drugs):
            values = [
                str(stock["drug_id"]),
                stock["batch_no"],
                stock["expiry"],
                str(stock["quantity"]),
                stock.get("drug_name") or "",
            ]
            for col, value in enumerate(values):
                self.wh_drug_table.setItem(row, col, QTableWidgetItem(value))
        self.wh_material_table.setRowCount(len(materials))
        for row, stock in enumerate(materials):
            values = [
                str(stock["item_id"]),
                stock.get("item_name") or "",
                stock["warehouse"],
                str(stock["quantity"]),
            ]
            for col, value in enumerate(values):
                self.wh_material_table.setItem(row, col, QTableWidgetItem(value))
        self.wh_msg.setText(f"药品批次 {len(drugs)}，物资 {len(materials)}")

    # ---------- 效期预警 ----------
    def _build_expiry_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        self.expiry_days = QSpinBox()
        self.expiry_days.setRange(1, 3650)
        self.expiry_days.setValue(90)
        refresh = QPushButton("刷新预警")
        refresh.clicked.connect(self._load_expiry_alerts)
        row.addWidget(QLabel("近效期天数"))
        row.addWidget(self.expiry_days)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(QLabel("已过期"))
        self.expired_table = QTableWidget(0, 5)
        self.expired_table.setHorizontalHeaderLabels(["药品", "库房", "批次", "效期", "数量"])
        layout.addWidget(self.expired_table)

        layout.addWidget(QLabel("近效期"))
        self.near_table = QTableWidget(0, 5)
        self.near_table.setHorizontalHeaderLabels(["药品", "库房", "批次", "效期", "剩余天数"])
        layout.addWidget(self.near_table)
        self.expiry_msg = QLabel("")
        self.expiry_msg.setWordWrap(True)
        layout.addWidget(self.expiry_msg)
        return page

    def _load_expiry_alerts(self) -> None:
        try:
            alerts = self.api.list_expiry_alerts(self.expiry_days.value())
        except ApiError as e:
            self.expiry_msg.setText(f"加载效期预警失败：{e.detail}")
            return
        expired = alerts.get("expired") or []
        near = alerts.get("near_expiry") or []
        self.expired_table.setRowCount(len(expired))
        for r, row in enumerate(expired):
            values = [
                row["name"], row["warehouse"], row["batch_no"],
                row["expiry"], str(row["quantity"]),
            ]
            for c, value in enumerate(values):
                self.expired_table.setItem(r, c, QTableWidgetItem(value))
        self.near_table.setRowCount(len(near))
        for r, row in enumerate(near):
            values = [
                row["name"], row["warehouse"], row["batch_no"],
                row["expiry"], str(row["days_left"]),
            ]
            for c, value in enumerate(values):
                self.near_table.setItem(r, c, QTableWidgetItem(value))
        self.expiry_msg.setText(f"过期 {len(expired)} 批，近效期 {len(near)} 批")

    # ---------- 追溯码 ----------
    def _build_trace_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("扫码（扫码枪扫描后回车录入）")
        form = QFormLayout(box)
        self.trace_mode = QComboBox()
        if self.role in ("warehouse", "admin"):
            self.trace_mode.addItem("入库扫码（总库登记）", "inbound")
            self.trace_mode.addItem("出库扫码（总库→药房）", "outbound")
        if self.role in ("pharmacist", "admin"):
            self.trace_mode.addItem("发药扫码（核销）", "dispense")
            self.trace_mode.addItem("退药扫码（回药房）", "return")
        form.addRow("模式", self.trace_mode)

        self.trace_drug = QComboBox()
        load_drug = QPushButton("刷新药品")
        load_drug.clicked.connect(self._load_trace_drugs)
        drug_row = QHBoxLayout()
        drug_row.addWidget(self.trace_drug)
        drug_row.addWidget(load_drug)
        self.trace_batch = QLineEdit()
        self.trace_batch.setPlaceholderText("批号（入库扫码必填）")
        form.addRow("药品", drug_row)
        form.addRow("批号", self.trace_batch)

        self.trace_encounter = QSpinBox()
        self.trace_encounter.setRange(0, 10_000_000)
        self.trace_encounter.setSpecialValueText("不关联就诊")
        form.addRow("就诊 ID", self.trace_encounter)

        scan_row = QHBoxLayout()
        self.trace_scan = QLineEdit()
        self.trace_scan.setPlaceholderText("扫描追溯码后回车")
        self.trace_scan.returnPressed.connect(self._add_trace_code)
        add = QPushButton("添加")
        add.clicked.connect(self._add_trace_code)
        scan_row.addWidget(self.trace_scan)
        scan_row.addWidget(add)
        form.addRow("扫码", scan_row)

        self.trace_codes_table = QTableWidget(0, 1)
        self.trace_codes_table.setHorizontalHeaderLabels(["本次扫码"])
        form.addRow("已扫", self.trace_codes_table)

        buttons = QHBoxLayout()
        submit = QPushButton("提交扫码")
        submit.clicked.connect(self._submit_trace)
        clear = QPushButton("清空")
        clear.clicked.connect(self._clear_trace)
        buttons.addWidget(submit)
        buttons.addWidget(clear)
        buttons.addStretch(1)
        form.addRow("", buttons)
        self.trace_msg = QLabel("")
        self.trace_msg.setWordWrap(True)
        form.addRow("", self.trace_msg)
        layout.addWidget(box)

        query_box = QGroupBox("追溯码查询")
        query_layout = QVBoxLayout(query_box)
        query_row = QHBoxLayout()
        self.trace_query = QLineEdit()
        self.trace_query.setPlaceholderText("追溯码（留空=最近 50 条）")
        query = QPushButton("查询")
        query.clicked.connect(self._query_trace)
        query_row.addWidget(self.trace_query)
        query_row.addWidget(query)
        query_layout.addLayout(query_row)
        self.trace_result_table = QTableWidget(0, 6)
        self.trace_result_table.setHorizontalHeaderLabels(
            ["追溯码", "药品ID", "批号", "库房", "状态", "患者"]
        )
        query_layout.addWidget(self.trace_result_table)
        self.trace_query_msg = QLabel("")
        self.trace_query_msg.setWordWrap(True)
        query_layout.addWidget(self.trace_query_msg)
        layout.addWidget(query_box)
        layout.addStretch(1)

        self.trace_scanned: list[str] = []
        self.trace_mode.currentIndexChanged.connect(self._update_trace_mode_hint)
        self._update_trace_mode_hint()
        return page

    def _update_trace_mode_hint(self) -> None:
        mode = self.trace_mode.currentData()
        inbound = mode == "inbound"
        self.trace_drug.setEnabled(inbound)
        self.trace_batch.setEnabled(inbound)
        self.trace_encounter.setEnabled(mode == "dispense")

    def _load_trace_drugs(self) -> None:
        try:
            drugs = self.api.list_drugs()
        except ApiError as e:
            self.trace_msg.setText(f"加载药品失败：{e.detail}")
            return
        self.trace_drug.clear()
        for drug in drugs:
            self.trace_drug.addItem(drug["name"], drug["id"])

    def _add_trace_code(self) -> None:
        code = self.trace_scan.text().strip()
        if not code:
            return
        if code in self.trace_scanned:
            self.trace_msg.setText(f"重复扫码：{code}")
        else:
            self.trace_scanned.append(code)
            self._refresh_trace_codes()
        self.trace_scan.clear()
        self.trace_scan.setFocus()

    def _refresh_trace_codes(self) -> None:
        self.trace_codes_table.setRowCount(len(self.trace_scanned))
        for row, code in enumerate(self.trace_scanned):
            self.trace_codes_table.setItem(row, 0, QTableWidgetItem(code))

    def _clear_trace(self) -> None:
        self.trace_scanned = []
        self._refresh_trace_codes()
        self.trace_msg.setText("")

    def _submit_trace(self) -> None:
        mode = self.trace_mode.currentData()
        if not mode:
            self.trace_msg.setText("当前角色没有扫码权限")
            return
        if not self.trace_scanned:
            self.trace_msg.setText("请先扫码")
            return
        payload = {"codes": self.trace_scanned}
        if mode == "inbound":
            drug_id = self.trace_drug.currentData()
            batch = self.trace_batch.text().strip()
            if not drug_id or not batch:
                self.trace_msg.setText("入库扫码请选择药品并填写批号")
                return
            payload["drug_id"] = drug_id
            payload["batch_no"] = batch
        if mode == "dispense" and self.trace_encounter.value() > 0:
            payload["encounter_id"] = self.trace_encounter.value()
        try:
            result = self.api.trace_scan(mode, payload)
        except ApiError as e:
            self.trace_msg.setText(f"扫码提交失败（{e.status_code}）：{e.detail}")
            return
        self.trace_msg.setText(result.get("message", "扫码成功"))
        self._clear_trace()
        self._query_trace()

    def _query_trace(self) -> None:
        code = self.trace_query.text().strip() or None
        try:
            rows = self.api.trace_codes(trace_code=code)
        except ApiError as e:
            self.trace_query_msg.setText(f"查询失败：{e.detail}")
            return
        self.trace_result_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = [
                item["trace_code"],
                str(item["drug_id"]),
                item["batch_no"],
                item["warehouse"],
                zh('trace_status', item["status"]),
                str(item.get("patient_id") or "—"),
            ]
            for col, value in enumerate(values):
                self.trace_result_table.setItem(row, col, QTableWidgetItem(value))
        self.trace_query_msg.setText(f"共 {len(rows)} 条")

    # ---------- 库存查询 ----------
    def _build_stock_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        refresh = QPushButton("刷新库存")
        refresh.clicked.connect(self._load_stocks)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)

        self.stock_table = QTableWidget(0, 6)
        self.stock_table.setHorizontalHeaderLabels(
            ["ID", "药品 ID", "批次", "效期", "数量", "货位"]
        )
        layout.addWidget(self.stock_table)

        self.stock_msg = QLabel("")
        self.stock_msg.setWordWrap(True)
        layout.addWidget(self.stock_msg)
        return page

    def _load_stocks(self) -> None:
        try:
            stocks = self.api.list_stocks()
        except ApiError as e:
            self.stock_msg.setText(f"加载库存失败：{e.detail}")
            return
        self.stock_table.setRowCount(len(stocks))
        for row, stock in enumerate(stocks):
            values = [
                str(stock["id"]),
                str(stock["drug_id"]),
                stock["batch_no"],
                stock["expiry"],
                str(stock["quantity"]),
                stock.get("location") or "",
            ]
            for col, value in enumerate(values):
                self.stock_table.setItem(row, col, QTableWidgetItem(value))
        self.stock_msg.setText(f"共 {len(stocks)} 个库存批次")

    # ---------- 医保目录 ----------
    def _build_catalog_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        self.catalog_keyword = QLineEdit()
        self.catalog_keyword.setPlaceholderText("药品名称 / 医保代码 / 厂家")
        self.catalog_category = QComboBox()
        for value, label in CATALOG_CATEGORIES:
            self.catalog_category.addItem(label, value)
        search = QPushButton("检索医保目录")
        search.clicked.connect(self._search_catalog)
        row.addWidget(self.catalog_keyword)
        row.addWidget(self.catalog_category)
        row.addWidget(search)
        layout.addLayout(row)

        self.catalog_table = QTableWidget(0, 6)
        self.catalog_table.setHorizontalHeaderLabels(
            ["医保代码", "名称", "剂型", "规格", "厂家", "类别"]
        )
        layout.addWidget(self.catalog_table)

        self.catalog_msg = QLabel("")
        self.catalog_msg.setWordWrap(True)
        layout.addWidget(self.catalog_msg)
        layout.addStretch(1)
        return page

    def _search_catalog(self) -> None:
        try:
            rows = self.api.search_insurance_catalog(
                q=self.catalog_keyword.text().strip() or None,
                category=self.catalog_category.currentData() or None,
            )
        except ApiError as e:
            self.catalog_msg.setText(f"检索失败（{e.status_code}）：{e.detail}")
            return
        self.catalog_table.setRowCount(len(rows))
        for row, drug in enumerate(rows):
            values = [
                drug["national_code"],
                drug["name"],
                drug.get("dosage_form") or "",
                drug.get("spec") or "",
                drug.get("manufacturer") or "",
                drug.get("category") or "",
            ]
            for col, value in enumerate(values):
                self.catalog_table.setItem(row, col, QTableWidgetItem(value))
        self.catalog_msg.setText(f"共 {len(rows)} 条目录记录")


    def _create_purchase_request(self) -> None:
        order = getattr(self, "handle_order", None)
        if not order:
            self.handle_msg.setText("请先选择出库单")
            return
        try:
            request = self.api.create_purchase_request_from_outbound(order["id"])
        except ApiError as e:
            self.handle_msg.setText(f"生成采购申请失败（{e.status_code}）：{e.detail}")
            return
        self.handle_msg.setText(
            f"已生成采购申请 {request['request_no']}（{request['status']}），等待机构审核"
        )
