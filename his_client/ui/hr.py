"""人事工作站：员工、医生、科室、登录账号。"""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.theme import apply_theme

ROLE_OPTIONS = [
    ("doctor", "医生"),
    ("nurse", "护士"),
    ("cashier", "收费员"),
    ("pharmacist", "药师"),
    ("warehouse", "库房管理员"),
    ("lab", "检验技师"),
    ("radiology", "影像技师"),
    ("archive", "病案管理员"),
    ("decoction", "煎药员"),
    ("surgery", "手术室护士"),
    ("treatment", "治疗室护士"),
    ("hr", "人事"),
    ("director", "院长"),
    ("admin", "管理员"),
]


def _role_combo() -> QComboBox:
    combo = QComboBox()
    for value, label in ROLE_OPTIONS:
        combo.addItem(label, value)
    return combo


class HrWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.employees: list[dict] = []
        self.doctors: list[dict] = []
        self.departments: list[dict] = []
        self.users: list[dict] = []
        tabs = SidebarTabs()
        tabs.addTab(self._build_employee_tab(), "员工档案")
        tabs.addTab(self._build_doctor_tab(), "医生管理")
        tabs.addTab(self._build_department_tab(), "科室管理")
        tabs.addTab(self._build_account_tab(), "账号管理")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        self._refresh_all()

    # ---------- 员工 ----------
    def _build_employee_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form_box = QGroupBox("新建员工")
        form_layout = QVBoxLayout(form_box)
        self.emp_no = QLineEdit()
        self.emp_name = QLineEdit()
        self.emp_dept = QComboBox()
        self.emp_role = _role_combo()
        self.emp_phone = QLineEdit()
        self.emp_email = QLineEdit()
        self.emp_hired = QDateEdit(QDate.currentDate())
        self.emp_hired.setCalendarPopup(True)
        self.emp_account = QCheckBox("同时创建登录账号")
        self.emp_username = QLineEdit()
        self.emp_password = QLineEdit()
        self.emp_password.setEchoMode(QLineEdit.Password)
        self.emp_username.setPlaceholderText("账号（勾选后必填）")
        self.emp_password.setPlaceholderText("密码（勾选后必填）")
        add = QPushButton("新增员工")
        add.clicked.connect(self._add_employee)
        columns = QHBoxLayout()
        left_form = QFormLayout()
        right_form = QFormLayout()
        left_form.addRow("工号", self.emp_no)
        left_form.addRow("姓名", self.emp_name)
        left_form.addRow("科室", self.emp_dept)
        left_form.addRow("岗位", self.emp_role)
        right_form.addRow("手机", self.emp_phone)
        right_form.addRow("邮箱", self.emp_email)
        right_form.addRow("入职日期", self.emp_hired)
        columns.addLayout(left_form, 1)
        columns.addLayout(right_form, 1)
        form_layout.addLayout(columns)
        account_row = QHBoxLayout()
        account_row.addWidget(self.emp_account)
        account_row.addWidget(self.emp_username)
        account_row.addWidget(self.emp_password)
        form_layout.addLayout(account_row)
        form_layout.addWidget(add)
        layout.addWidget(form_box)

        self.emp_table = QTableWidget(0, 7)
        self.emp_table.setHorizontalHeaderLabels(
            ["工号", "姓名", "科室", "岗位", "手机", "状态", "入职"]
        )
        self.emp_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.emp_table, 1)
        actions = QHBoxLayout()
        resign = QPushButton("办理离职")
        resign.clicked.connect(self._resign_employee)
        refresh = QPushButton("刷新员工")
        refresh.clicked.connect(self._load_employees)
        actions.addWidget(resign)
        actions.addWidget(refresh)
        self.emp_msg = QLabel("")
        actions.addWidget(self.emp_msg, 1)
        layout.addLayout(actions)
        return page

    def _load_departments(self) -> None:
        try:
            self.departments = self.api.list_departments(include_inactive=True)
        except ApiError as e:
            self.emp_msg.setText(f"科室加载失败：{e.detail}")
            return
        for combo in (self.emp_dept, self.doc_dept):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("未指定", None)
            for row in self.departments:
                label = row["name"] + ("" if row.get("active", True) else "（停用）")
                combo.addItem(label, row["id"])
            idx = combo.findData(current)
            combo.setCurrentIndex(max(0, idx))
            combo.blockSignals(False)

    def _load_employees(self) -> None:
        try:
            self.employees = self.api.list_employees()
        except ApiError as e:
            self.emp_msg.setText(f"员工加载失败：{e.detail}")
            return
        dept_names = {row["id"]: row["name"] for row in self.departments}
        role_names = dict(ROLE_OPTIONS)
        self.emp_table.setRowCount(len(self.employees))
        for i, row in enumerate(self.employees):
            values = [
                row.get("employee_no", ""),
                row.get("name", ""),
                dept_names.get(row.get("department_id"), "—"),
                role_names.get(row.get("role"), row.get("role", "")),
                row.get("phone", ""),
                "在职" if row.get("status") == "active" else "已离职",
                str(row.get("hired_at") or ""),
            ]
            for col, value in enumerate(values):
                self.emp_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.emp_msg.setText(f"员工 {len(self.employees)} 人")

    def _add_employee(self) -> None:
        no = self.emp_no.text().strip()
        name = self.emp_name.text().strip()
        if not no or not name:
            self.emp_msg.setText("工号和姓名必填")
            return
        payload = {
            "employee_no": no,
            "name": name,
            "department_id": self.emp_dept.currentData(),
            "role": self.emp_role.currentData(),
            "phone": self.emp_phone.text().strip(),
            "email": self.emp_email.text().strip(),
            "hired_at": self.emp_hired.date().toString("yyyy-MM-dd"),
        }
        try:
            employee = self.api.create_employee(payload)
        except ApiError as e:
            self.emp_msg.setText(f"新增失败（{e.status_code}）：{e.detail}")
            return
        if self.emp_account.isChecked():
            username = self.emp_username.text().strip()
            password = self.emp_password.text()
            if not username or not password:
                self.emp_msg.setText(f"员工 {employee['employee_no']} 已建，但账号/密码未填")
            else:
                try:
                    self.api.create_user(
                        {
                            "username": username,
                            "password": password,
                            "role": self.emp_role.currentData(),
                            "display_name": name,
                            "employee_id": employee["id"],
                        }
                    )
                    self.emp_msg.setText(f"员工 {employee['employee_no']} 和账号已创建")
                except ApiError as e:
                    self.emp_msg.setText(f"员工已建，账号失败（{e.status_code}）：{e.detail}")
        else:
            self.emp_msg.setText(f"员工 {employee['employee_no']} 已创建")
        self.emp_no.clear()
        self.emp_name.clear()
        self.emp_username.clear()
        self.emp_password.clear()
        self._refresh_all()

    def _resign_employee(self) -> None:
        row = self.emp_table.currentRow()
        if not (0 <= row < len(self.employees)):
            self.emp_msg.setText("请先选择员工")
            return
        employee = self.employees[row]
        if QMessageBox.question(
            self, "确认离职", f"确认给 {employee['name']} 办理离职？"
        ) != QMessageBox.Yes:
            return
        try:
            self.api.resign_employee(employee["id"])
        except ApiError as e:
            self.emp_msg.setText(f"离职失败（{e.status_code}）：{e.detail}")
            return
        self._load_employees()

    # ---------- 医生 ----------
    def _build_doctor_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("新增医生")
        form = QFormLayout(box)
        self.doc_name = QLineEdit()
        self.doc_dept = QComboBox()
        add = QPushButton("新增医生")
        add.clicked.connect(self._add_doctor)
        form.addRow("姓名", self.doc_name)
        form.addRow("科室", self.doc_dept)
        form.addRow("", add)
        layout.addWidget(box)
        self.doc_table = QTableWidget(0, 4)
        self.doc_table.setHorizontalHeaderLabels(["ID", "姓名", "科室", "状态"])
        self.doc_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.doc_table, 1)
        actions = QHBoxLayout()
        dismiss = QPushButton("停用/辞退医生")
        dismiss.clicked.connect(self._dismiss_doctor)
        refresh = QPushButton("刷新医生")
        refresh.clicked.connect(self._load_doctors)
        actions.addWidget(dismiss)
        actions.addWidget(refresh)
        self.doc_msg = QLabel("")
        actions.addWidget(self.doc_msg, 1)
        layout.addLayout(actions)
        return page

    def _load_doctors(self) -> None:
        try:
            self.doctors = self.api.list_doctors(include_inactive=True)
        except ApiError as e:
            self.doc_msg.setText(f"医生加载失败：{e.detail}")
            return
        dept_names = {row["id"]: row["name"] for row in self.departments}
        self.doc_table.setRowCount(len(self.doctors))
        for i, row in enumerate(self.doctors):
            values = [
                str(row["id"]),
                row["name"],
                dept_names.get(row.get("department_id"), "—"),
                "在职" if row.get("active", True) else "已停用",
            ]
            for col, value in enumerate(values):
                self.doc_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.doc_msg.setText(f"医生 {len(self.doctors)} 人")

    def _add_doctor(self) -> None:
        name = self.doc_name.text().strip()
        dept_id = self.doc_dept.currentData()
        if not name or not dept_id:
            self.doc_msg.setText("姓名和科室必填")
            return
        try:
            self.api.create_doctor(name, dept_id)
        except ApiError as e:
            self.doc_msg.setText(f"新增失败（{e.status_code}）：{e.detail}")
            return
        self.doc_name.clear()
        self._load_doctors()

    def _dismiss_doctor(self) -> None:
        row = self.doc_table.currentRow()
        if not (0 <= row < len(self.doctors)):
            self.doc_msg.setText("请先选择医生")
            return
        doctor = self.doctors[row]
        if QMessageBox.question(
            self, "确认停用", f"确认停用/辞退医生 {doctor['name']}？"
        ) != QMessageBox.Yes:
            return
        try:
            self.api.delete_doctor(doctor["id"])
        except ApiError as e:
            self.doc_msg.setText(f"停用失败（{e.status_code}）：{e.detail}")
            return
        self._load_doctors()

    # ---------- 科室 ----------
    def _build_department_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("新增科室")
        row = QHBoxLayout(box)
        self.dept_name = QLineEdit()
        self.dept_name.setPlaceholderText("科室名称")
        add = QPushButton("新增科室")
        add.clicked.connect(self._add_department)
        row.addWidget(self.dept_name, 1)
        row.addWidget(add)
        layout.addWidget(box)
        self.dept_table = QTableWidget(0, 3)
        self.dept_table.setHorizontalHeaderLabels(["ID", "名称", "状态"])
        self.dept_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.dept_table, 1)
        actions = QHBoxLayout()
        disable = QPushButton("停用科室")
        disable.clicked.connect(self._disable_department)
        refresh = QPushButton("刷新科室")
        refresh.clicked.connect(self._load_departments)
        actions.addWidget(disable)
        actions.addWidget(refresh)
        self.dept_msg = QLabel("")
        actions.addWidget(self.dept_msg, 1)
        layout.addLayout(actions)
        return page

    def _load_department_table(self) -> None:
        self.dept_table.setRowCount(len(self.departments))
        for i, row in enumerate(self.departments):
            values = [
                str(row["id"]),
                row["name"],
                "启用" if row.get("active", True) else "已停用",
            ]
            for col, value in enumerate(values):
                self.dept_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.dept_msg.setText(f"科室 {len(self.departments)} 个")

    def _add_department(self) -> None:
        name = self.dept_name.text().strip()
        if not name:
            self.dept_msg.setText("科室名称必填")
            return
        try:
            self.api.create_department(name)
        except ApiError as e:
            self.dept_msg.setText(f"新增失败（{e.status_code}）：{e.detail}")
            return
        self.dept_name.clear()
        self._load_departments()
        self._load_department_table()

    def _disable_department(self) -> None:
        row = self.dept_table.currentRow()
        if not (0 <= row < len(self.departments)):
            self.dept_msg.setText("请先选择科室")
            return
        dept = self.departments[row]
        if QMessageBox.question(
            self, "确认停用", f"确认停用科室 {dept['name']}？"
        ) != QMessageBox.Yes:
            return
        try:
            self.api.delete_department(dept["id"])
        except ApiError as e:
            self.dept_msg.setText(f"停用失败（{e.status_code}）：{e.detail}")
            return
        self._load_departments()
        self._load_department_table()

    # ---------- 账号 ----------
    def _build_account_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("创建登录账号")
        form = QFormLayout(box)
        self.acc_username = QLineEdit()
        self.acc_password = QLineEdit()
        self.acc_password.setEchoMode(QLineEdit.Password)
        self.acc_display = QLineEdit()
        self.acc_role = _role_combo()
        self.acc_employee = QSpinBox()
        self.acc_employee.setRange(0, 10_000_000)
        self.acc_employee.setSpecialValueText("不关联员工")
        add = QPushButton("创建账号")
        add.clicked.connect(self._add_account)
        form.addRow("账号", self.acc_username)
        form.addRow("密码", self.acc_password)
        form.addRow("显示名", self.acc_display)
        form.addRow("角色", self.acc_role)
        form.addRow("关联员工 ID", self.acc_employee)
        form.addRow("", add)
        layout.addWidget(box)
        self.acc_table = QTableWidget(0, 5)
        self.acc_table.setHorizontalHeaderLabels(["ID", "账号", "显示名", "角色", "员工 ID"])
        self.acc_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.acc_table, 1)
        actions = QHBoxLayout()
        refresh = QPushButton("刷新账号")
        refresh.clicked.connect(self._load_accounts)
        actions.addWidget(refresh)
        self.acc_msg = QLabel("")
        actions.addWidget(self.acc_msg, 1)
        layout.addLayout(actions)
        return page

    def _load_accounts(self) -> None:
        try:
            self.users = self.api.list_users()
        except ApiError as e:
            self.acc_msg.setText(f"账号加载失败：{e.detail}")
            return
        role_names = dict(ROLE_OPTIONS)
        self.acc_table.setRowCount(len(self.users))
        for i, row in enumerate(self.users):
            values = [
                str(row["id"]),
                row["username"],
                row.get("display_name") or "",
                role_names.get(row.get("role"), row.get("role", "")),
                str(row.get("employee_id") or ""),
            ]
            for col, value in enumerate(values):
                self.acc_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.acc_msg.setText(f"账号 {len(self.users)} 个")

    def _add_account(self) -> None:
        username = self.acc_username.text().strip()
        password = self.acc_password.text()
        if not username or not password:
            self.acc_msg.setText("账号和密码必填")
            return
        payload = {
            "username": username,
            "password": password,
            "role": self.acc_role.currentData(),
            "display_name": self.acc_display.text().strip() or username,
            "employee_id": self.acc_employee.value() or None,
        }
        try:
            self.api.create_user(payload)
        except ApiError as e:
            self.acc_msg.setText(f"创建失败（{e.status_code}）：{e.detail}")
            return
        self.acc_username.clear()
        self.acc_password.clear()
        self.acc_display.clear()
        self._load_accounts()

    def _refresh_all(self) -> None:
        self._load_departments()
        self._load_department_table()
        self._load_employees()
        self._load_doctors()
        self._load_accounts()
