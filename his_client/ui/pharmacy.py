"""药房工作站：入库单（收货/验收/入库）、发药/退药、库存查询、医保目录查询。"""
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
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.pending_items: list[dict] = []
        self.outbound_items: list[dict] = []
        self.current_order: dict | None = None

        tabs = QTabWidget()
        tabs.addTab(self._build_inbound_tab(), "入库单")
        tabs.addTab(self._build_outbound_tab(), "领用出库")
        tabs.addTab(self._build_dispense_tab(), "发药 / 退药")
        tabs.addTab(self._build_stock_tab(), "库存查询")
        tabs.addTab(self._build_catalog_tab(), "医保目录")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

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
        for w in (self.in_drug, load_drugs, self.in_batch, self.in_expiry, self.in_qty, self.in_price, self.in_storage, self.in_location, add_drug):
            drug_row.addWidget(w)
        items_layout.addWidget(QLabel("药品行：药品 / 批号 / 效期 / 数量 / 单价 / 储存 / 货位"))
        items_layout.addLayout(drug_row)

        material_row = QHBoxLayout()
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
        for w in (self.in_material, load_materials, self.in_m_qty, self.in_m_price, self.in_warehouse, add_material):
            material_row.addWidget(w)
        items_layout.addWidget(QLabel("物资行：器械/耗材/办公 / 数量 / 单价 / 库房"))
        items_layout.addLayout(material_row)

        self.pending_table = QTableWidget(0, 6)
        self.pending_table.setHorizontalHeaderLabels(
            ["类型", "名称", "批号", "数量", "单价", "金额"]
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
        try:
            drugs = self.api.list_drugs()
        except ApiError as e:
            self.in_msg.setText(f"加载药品失败：{e.detail}")
            return
        self.in_drug.clear()
        for drug in drugs:
            self.in_drug.addItem(f"{drug['name']}（{drug['base_price']:.2f}）", drug["id"])

    def _load_materials(self) -> None:
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

    def _add_drug_item(self) -> None:
        drug_id = self.in_drug.currentData()
        if not drug_id:
            self.in_msg.setText("请先刷新并选择药品")
            return
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
        }
        self.pending_items.append(item)
        self._refresh_pending()
        self.in_msg.setText("已添加药品行，可继续添加或提交")

    def _add_material_item(self) -> None:
        material_id = self.in_material.currentData()
        if not material_id:
            self.in_msg.setText("请先刷新并选择物资")
            return
        price = self.in_m_price.text().strip()
        item = {
            "kind": "material",
            "material_id": material_id,
            "quantity": self.in_m_qty.value(),
            "unit_price": float(price) if price else 0,
            "warehouse": self.in_warehouse.text().strip() or "总库",
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
            f"入库单已创建：{order['order_no']}（{order['status']}），等待验收"
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
                order["status"],
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
            f"当前入库单 {order['order_no']}（{order['status']}），明细 {len(items)} 行"
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
        submit = QPushButton("发药")
        submit.clicked.connect(self._dispense)
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.disp_encounter_id)
        row.addWidget(submit)
        layout.addWidget(box)

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
        return page

    def _dispense(self) -> None:
        try:
            record = self.api.dispense(self.disp_encounter_id.value())
        except ApiError as e:
            self.disp_msg.setText(f"发药失败（{e.status_code}）：{e.detail}")
            return
        self.disp_msg.setText(
            f"发药成功：记录 {record['id']}，就诊 {record['encounter_id']}（{record['status']}）"
        )
        self.return_dispense_id.setValue(record["id"])

    def _return_dispense(self) -> None:
        try:
            record = self.api.return_dispense(self.return_dispense_id.value())
        except ApiError as e:
            self.return_msg.setText(f"退药失败（{e.status_code}）：{e.detail}")
            return
        self.return_msg.setText(
            f"退药成功：记录 {record['id']}（{record['status']}），库存已回补"
        )

    # ---------- 领用出库（向库房申请） ----------
    def _build_outbound_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form_box = QGroupBox("向库房申请领用（审核/出库由库房操作）")
        form = QFormLayout(form_box)
        self.out_target_type = QComboBox()
        self.out_target_type.addItem("药房", "pharmacy")
        self.out_target_type.addItem("科室", "department")
        self.out_target_name = QLineEdit("药房")
        self.out_note = QLineEdit()
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
            "outbound_type": "requisition",
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
            f"领用申请已提交：{order['outbound_no']}（{order['status']}），等待库房审核"
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
                order["status"],
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
        self.out_list_msg.setText(f"出库单 {order['outbound_no']}（{order['status']}）")

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
