"""患者 360：基本信息、就诊时间线、预约、病案、收费。"""
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme
from his_client.labels import zh
from his_client.ui.sidebar_tabs import SidebarTabs


class Patient360Widget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.patients: list[dict] = []
        self.profile: dict | None = None

        layout = QVBoxLayout(self)
        search = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("姓名")
        self.id_number = QLineEdit()
        self.id_number.setPlaceholderText("身份证号")
        button = QPushButton("查询患者")
        button.clicked.connect(self._search)
        search.addWidget(QLabel("姓名"))
        search.addWidget(self.name)
        search.addWidget(QLabel("身份证号"))
        search.addWidget(self.id_number)
        search.addWidget(button)
        layout.addLayout(search)

        self.patient_table = QTableWidget(0, 3)
        self.patient_table.setHorizontalHeaderLabels(["患者 ID", "姓名", "身份证号"])
        self.patient_table.setMaximumHeight(130)
        self.patient_table.cellClicked.connect(self._select_patient)
        layout.addWidget(self.patient_table)

        self.header = QLabel("请选择患者")
        self.header.setStyleSheet("font-size:16px;font-weight:bold")
        layout.addWidget(self.header)
        self.stats = QLabel("")
        self.stats.setWordWrap(True)
        layout.addWidget(self.stats)

        self.tabs = SidebarTabs()
        self.enc_table = QTableWidget(0, 6)
        self.enc_table.setHorizontalHeaderLabels(
            ["就诊", "时间", "诊断", "医生", "处方", "检验"]
        )
        self.enc_table.cellClicked.connect(self._select_encounter)
        self.tabs.addTab(self.enc_table, "就诊记录")
        self.appt_table = QTableWidget(0, 5)
        self.appt_table.setHorizontalHeaderLabels(
            ["预约", "医生", "状态", "预约时间", "挂号"]
        )
        self.tabs.addTab(self.appt_table, "预约记录")
        self.archive_table = QTableWidget(0, 5)
        self.archive_table.setHorizontalHeaderLabels(
            ["病案号", "类型", "状态", "库位", "归档时间"]
        )
        self.tabs.addTab(self.archive_table, "病案档案")
        self.money_table = QTableWidget(0, 4)
        self.money_table.setHorizontalHeaderLabels(["就诊", "项目", "金额", "状态"])
        self.tabs.addTab(self.money_table, "收费明细")
        layout.addWidget(self.tabs, 1)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)

    def _search(self) -> None:
        try:
            found = self.api.list_patients(
                name=self.name.text().strip() or None,
                id_number=self.id_number.text().strip() or None,
            )
        except ApiError as e:
            self.detail.setText(f"查询失败（{e.status_code}）：{e.detail}")
            return
        self.patients = found
        self.patient_table.setRowCount(len(found))
        for row, patient in enumerate(found):
            values = [str(patient["id"]), patient["name"], patient.get("id_number", "")]
            for col, value in enumerate(values):
                self.patient_table.setItem(row, col, QTableWidgetItem(value))
        self.detail.setText(f"共 {len(found)} 位患者，点击选择查看 360")

    def _select_patient(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self.patients)):
            return
        patient = self.patients[row]
        try:
            self.profile = self.api.patient_profile(patient["id"])
        except ApiError as e:
            self.detail.setText(f"加载 360 失败（{e.status_code}）：{e.detail}")
            return
        data = self.profile
        info = data["patient"]
        stats = data["stats"]
        self.header.setText(f"{info['name']}（ID {info['id']}）· {info.get('phone') or '无电话'}")
        self.stats.setText(
            f"就诊 {stats['visit_count']} 次　预约 {stats['appointment_count']} 次　"
            f"病案 {stats['archive_count']} 份　处方 {stats['prescription_count']} 张　"
            f"检验 {stats['lab_count']} 项　累计实收 {stats['total_paid']:.2f} 元　"
            f"待缴 {stats['outstanding']:.2f} 元　最近就诊 {str(stats.get('last_visit') or '—')[:16]}"
        )
        encounters = data["encounters"]
        self.enc_table.setRowCount(len(encounters))
        for row, encounter in enumerate(encounters):
            values = [
                str(encounter["id"]),
                str(encounter["visited_at"])[:16].replace("T", " "),
                encounter["diagnosis"] or "—",
                encounter["doctor_name"],
                str(len(encounter["prescriptions"])),
                str(len(encounter["lab_requests"])),
            ]
            for col, value in enumerate(values):
                self.enc_table.setItem(row, col, QTableWidgetItem(str(value)))
        appointments = data["appointments"]
        self.appt_table.setRowCount(len(appointments))
        for row, item in enumerate(appointments):
            values = [
                str(item["id"]),
                item["doctor_name"],
                {"booked": "已预约", "checked_in": "已取号", "no_show": "爽约", "cancelled": "已取消"}.get(
                    item["status"], item["status"]
                ),
                str(item["created_at"])[:16].replace("T", " "),
                str(item.get("registration_id") or "—"),
            ]
            for col, value in enumerate(values):
                self.appt_table.setItem(row, col, QTableWidgetItem(str(value)))
        archives = data["archives"]
        self.archive_table.setRowCount(len(archives))
        for row, item in enumerate(archives):
            values = [
                item.get("archive_no") or "—",
                {"outpatient": "门诊", "inpatient": "住院", "emergency": "急诊"}.get(
                    item["record_type"], item["record_type"]
                ),
                {
                    "draft": "已建档",
                    "archived": "已归档",
                    "borrowed": "已借出",
                    "sealed": "已封存",
                    "destroyed": "已销毁",
                }.get(item["status"], item["status"]),
                item["storage_location"] or "—",
                str(item.get("archived_at") or "")[:16].replace("T", " "),
            ]
            for col, value in enumerate(values):
                self.archive_table.setItem(row, col, QTableWidgetItem(str(value)))
        money_rows = []
        for encounter in encounters:
            for charge in encounter["charges"]:
                money_rows.append(
                    [
                        str(encounter["id"]),
                        charge["item_name"],
                        f"{charge['amount']:.2f}",
                        zh("charge_status", charge["status"]),
                    ]
                )
        self.money_table.setRowCount(len(money_rows))
        for row, values in enumerate(money_rows):
            for col, value in enumerate(values):
                self.money_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.detail.setText("患者 360 已加载")

    def _select_encounter(self, row: int, _col: int) -> None:
        if not self.profile or not (0 <= row < len(self.profile["encounters"])):
            return
        encounter = self.profile["encounters"][row]
        record = encounter.get("medical_record") or {}
        self.detail.setText(
            f"就诊 {encounter['id']} · {encounter['diagnosis']}　"
            f"病历：{'已签名' if record.get('signed_by') else '未签名'}　"
            f"处方 {len(encounter['prescriptions'])} 张　检验 {len(encounter['lab_requests'])} 项　"
            f"收费 {len(encounter['charges'])} 项"
        )
