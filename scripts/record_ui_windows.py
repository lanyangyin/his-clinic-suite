"""一身份一窗口的全流程操作录像：医生站挂号、历史诊疗、收费、入库、领用、发药。

运行：
    .venv\\Scripts\\python.exe scripts\\record_ui_windows.py
产出：
    docs/全流程操作录像.mp4（覆盖旧视频）
"""
import base64
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.cashier import CashierWidget  # noqa: E402
from his_client.ui.doctor import DoctorWidget  # noqa: E402
from his_client.ui.lab import LabWidget  # noqa: E402
from his_client.ui.nurse import NurseWidget  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402
from his_client.ui.treatment_room import TreatmentRoomWidget  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "ui_window_frames"
VIDEO_PATH = ROOT / "docs" / "全流程操作录像.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class Api:
    def __init__(self, username: str, password: str):
        self.session = requests.Session()
        self.session.trust_env = False
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers["Authorization"] = f"Basic {token}"

    def call(self, method: str, path: str, **kwargs):
        response = self.session.request(method, BASE + path, timeout=30, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:200]}")
        return response.json() if response.text else {}


class RoleWindow(QMainWindow):
    def __init__(self, title: str, widget: QWidget):
        super().__init__()
        self.setWindowTitle(title)
        self.setCentralWidget(widget)
        self.resize(1000, 620)


class CaptionBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("准备开始…")
        self.label.setStyleSheet(
            "font-size:20px;font-weight:bold;color:#0f172a;background:#e0f2fe;"
            "border:2px solid #0284c7;border-radius:8px;padding:10px"
        )
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.resize(1500, 52)

    def set_text(self, text: str) -> None:
        self.label.setText(text)


class DemoController:
    def __init__(self):
        self.admin = Api("admin", "admin123")
        self.cashier_api = Api("cashier", "cashier123")
        self.doctor_api = Api("doctor", "doctor123")
        self.nurse_api = Api("nurse", "nurse123")
        self.lab_api = Api("lab", "lab123")
        self.pharmacist_api = Api("pharmacist", "pharm123")
        self.warehouse_api = Api("warehouse", "warehouse123")

        self.warehouse = PharmacyWidget(
            ApiClient(BASE, "warehouse", "warehouse123"), role="warehouse"
        )
        self.cashier = CashierWidget(ApiClient(BASE, "cashier", "cashier123"))
        self.nurse = NurseWidget(ApiClient(BASE, "nurse", "nurse123"))
        self.doctor = DoctorWidget(ApiClient(BASE, "doctor", "doctor123"))
        self.pharmacy = PharmacyWidget(
            ApiClient(BASE, "pharmacist", "pharm123"), role="pharmacist"
        )
        self.treatment = TreatmentRoomWidget(
            ApiClient(BASE, "treatment", "treatment123")
        )
        self.lab = LabWidget(ApiClient(BASE, "lab", "lab123"))
        self.windows = {
            self.warehouse: RoleWindow("库房工作站 · warehouse", self.warehouse),
            self.cashier: RoleWindow("收费员工作站 · cashier", self.cashier),
            self.nurse: RoleWindow("护士工作站 · nurse", self.nurse),
            self.doctor: RoleWindow("医生工作站 · doctor", self.doctor),
            self.pharmacy: RoleWindow("药房工作站 · pharmacist", self.pharmacy),
            self.treatment: RoleWindow("治疗室工作站 · treatment", self.treatment),
            self.lab: RoleWindow("检验工作站 · lab", self.lab),
        }
        self.caption = CaptionBar()
        self.screen = QApplication.primaryScreen()
        self.geo = self.screen.geometry()
        self.cap_geo = self.screen.availableGeometry()
        self.caption.move(self.cap_geo.x() + 20, self.cap_geo.y() + 34)
        self.caption.resize(self.cap_geo.width() - 40, 48)

        self.frame_index = 0
        self.point: QPoint | None = None
        self.point_until = 0.0
        self.frames: list[Path] = []
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture)
        self.suffix = datetime.now().strftime("%m%d%H%M%S")
        self.success = False

    # ---------- 窗口/录制 ----------
    def tile_windows(self) -> None:
        width = self.cap_geo.width() // 4
        height = self.cap_geo.height() // 2
        positions = [
            (0, 0), (width, 0), (width * 2, 0), (width * 3, 0),
            (0, height), (width, height), (width * 2, height),
        ]
        for window, (x, y) in zip(self.windows.values(), positions):
            window.showNormal()
            window.setGeometry(self.cap_geo.x() + x, self.cap_geo.y() + y, width, height)
            window.show()
        self.caption.show()
        self.caption.raise_()

    def activate(self, widget: QWidget) -> None:
        window = self.windows[widget]
        window.showMaximized()
        window.raise_()
        window.activateWindow()
        self.caption.show()
        self.caption.raise_()
        self.wait(0.5)

    def wait(self, seconds: float = 0.7) -> None:
        QTest.qWait(int(seconds * 1000))

    def scene(self, text: str, widget: QWidget | None = None) -> None:
        print(f"[场景] {text}", flush=True)
        if widget is not None:
            self.activate(widget)
        self.caption.set_text(text)
        self.caption.raise_()
        self.wait(1.0)

    def switch_inner(self, root: QWidget, text: str) -> QWidget:
        tabs = root.findChild(QTabWidget)
        if tabs:
            for index in range(tabs.count()):
                if text in tabs.tabText(index):
                    tabs.setCurrentIndex(index)
                    self.wait(0.4)
                    return tabs.widget(index)
        return root

    def highlight(self, widget: QWidget) -> None:
        try:
            self.point = widget.mapToGlobal(widget.rect().center())
            self.point_until = time.time() + 0.9
        except Exception:
            self.point = None

    def click(self, container: QWidget, text: str) -> None:
        print(f"  -> 点击：{text}", flush=True)
        for button in container.findChildren(QPushButton):
            if button.text().strip() == text and button.isVisible():
                self.highlight(button)
                self.wait(0.15)
                QTest.mouseClick(button, Qt.LeftButton)
                self.wait(0.8)
                return
        raise RuntimeError(f"找不到按钮：{text}")

    def set_combo(self, combo: QComboBox, contains: str) -> None:
        for index in range(combo.count()):
            if contains in combo.itemText(index):
                combo.setCurrentIndex(index)
                self.highlight(combo)
                self.wait(0.25)
                return
        raise RuntimeError(f"下拉框找不到：{contains}")

    def capture(self) -> None:
        pixmap = self.screen.grabWindow(0)
        if self.point is not None and time.time() < self.point_until:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            scale_x = pixmap.width() / max(1, self.geo.width())
            scale_y = pixmap.height() / max(1, self.geo.height())
            point = QPoint(
                int((self.point.x() - self.geo.x()) * scale_x),
                int((self.point.y() - self.geo.y()) * scale_y),
            )
            painter.setPen(QPen(QColor("#ef4444"), 4))
            painter.setBrush(QColor(239, 68, 68, 80))
            painter.drawEllipse(point, 18, 18)
            painter.setBrush(QColor("#ef4444"))
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPoint(point.x() + 12, point.y()),
                        QPoint(point.x() + 28, point.y() + 7),
                        QPoint(point.x() + 14, point.y() + 18),
                    ]
                )
            )
            painter.end()
        image = pixmap.toImage().scaled(
            1600, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.frame_index += 1
        path = FRAME_DIR / f"frame_{self.frame_index:04d}.jpg"
        image.save(str(path), "JPEG", 86)
        self.frames.append(path)

    # ---------- 数据准备 ----------
    def setup(self) -> None:
        self.future = (date.today() + timedelta(days=900)).isoformat()
        self.supplier = self.admin.call(
            "POST", "/suppliers/",
            json={"code": f"WINDEMO-SUP-{self.suffix}", "name": f"演示供应商{self.suffix}"},
        )
        department = self.admin.call(
            "POST", "/departments/", json={"name": f"演示内科{self.suffix}"}
        )
        self.doctor_row = self.admin.call(
            "POST", "/doctors/",
            json={"name": f"演示医生{self.suffix}", "department_id": department["id"]},
        )
        self.drug = self.admin.call(
            "POST", "/drugs/",
            json={"name": f"演示阿莫西林{self.suffix}", "base_price": 12.5, "insurance_ratio": 0.8},
        )
        self.lab_item = self.admin.call(
            "POST", "/lab/items/",
            json={"code": f"WDEMO{self.suffix[-6:]}", "name": f"血常规{self.suffix}", "price": 20.0},
        )
        self.treat_item = self.admin.call(
            "POST", "/charges/items/",
            json={
                "code": f"WDEMO-TRT-{self.suffix}",
                "name": f"雾化治疗{self.suffix}",
                "category": "treatment",
                "price": 30.0,
                "insurance_ratio": 0.0,
            },
        )
        self.wound_item = self.admin.call(
            "POST", "/charges/items/",
            json={
                "code": f"WDEMO-WOUND-{self.suffix}",
                "name": f"清创缝合{self.suffix}",
                "category": "treatment",
                "price": 80.0,
                "insurance_ratio": 0.0,
            },
        )
        self.admin.call(
            "PUT", "/treatment-room/templates/debridement",
            json={
                "charge_item_id": self.wound_item["id"],
                "price": 80.0,
                "materials": [],
                "active": True,
            },
        )

    def seed_prior_visit(self, patient_id: int) -> None:
        """镜头外补一次历史就诊，用于演示医生调阅既往病历/处方/检验/治疗。"""
        reg = self.cashier_api.call(
            "POST", "/registrations/",
            json={"patient_id": patient_id, "doctor_id": self.doctor_row["id"]},
        )
        enc = self.doctor_api.call(
            "POST", "/encounters/",
            json={"registration_id": reg["id"], "diagnosis": "高血压复诊"},
        )
        self.doctor_api.call(
            "POST", f"/encounters/{enc['id']}/medical-record",
            json={
                "chief_complaint": "头晕 1 周",
                "present_illness": "晨起头晕，血压 150/95mmHg",
                "past_history": "高血压 5 年，规律服药",
                "physical_exam": "心肺未见异常",
                "treatment_advice": "低盐饮食，继续降压治疗",
            },
        )
        self.doctor_api.call(
            "POST", f"/encounters/{enc['id']}/medical-record/sign"
        )
        self.doctor_api.call(
            "POST", f"/encounters/{enc['id']}/prescriptions",
            json={
                "drug_id": self.drug["id"], "quantity": 1,
                "dosage": "1片", "frequency": "qd", "route": "口服", "days": 7,
            },
        )
        lab = self.doctor_api.call(
            "POST", f"/lab/encounters/{enc['id']}/lab-requests",
            json={"item_id": self.lab_item["id"]},
        )
        treatment = self.doctor_api.call(
            "POST", f"/treatments/encounters/{enc['id']}",
            json={"item_id": self.treat_item["id"], "quantity": 1},
        )
        self.lab_api.call(
            "POST", f"/lab/requests/{lab['id']}/report",
            json={"result": "血压相关指标正常"},
        )
        self.nurse_api.call("POST", f"/treatments/{treatment['id']}/execute")
        # 历史就诊挂起，避免占用医生“当前就诊”互斥位
        self.doctor_api.call("POST", f"/encounters/{enc['id']}/pause")
        self.prior_encounter_id = enc["id"]

    # ---------- 演示流程 ----------
    def run_flow(self) -> None:
        self.scene("多账号演示：库房 / 收费 / 护士 / 医生 / 药房，各一个独立窗口")
        self.tile_windows()
        self.wait(2.0)

        self.scene("① 收费员窗口：患者建档", self.cashier)
        patient_tab = self.switch_inner(self.cashier, "患者建档")
        self.cashier.p_name.setText(f"演示患者{self.suffix}")
        self.cashier.p_gender.setCurrentIndex(self.cashier.p_gender.findData("male"))
        self.cashier.p_id_number.setText(f"1101011996{self.suffix[-8:]}")
        self.cashier.p_birth_date.setText("1996-05-20")
        self.cashier.p_phone.setText("13800000000")
        self.cashier.p_address.setText("北京市东城区演示街道 1 号")
        self.cashier.p_emergency_name.setText("演示家属")
        self.cashier.p_emergency_relation.setText("配偶")
        self.cashier.p_emergency_phone.setText("13900001234")
        self.cashier.p_privacy.setChecked(True)
        self.click(patient_tab, "建档")
        patients = self.cashier_api.call(
            "GET", "/patients/", params={"id_number": f"1101011996{self.suffix[-8:]}"}
        )
        self.patient_id = patients[0]["id"]
        self.seed_prior_visit(self.patient_id)
        self.scene("✅ 建档完成（该患者已有一次历史就诊，供医生调阅）")

        self.scene("② 医生窗口：现场挂号（患者直接在医生站挂号）", self.doctor)
        reg_tab = self.switch_inner(self.doctor, "挂号")
        self.doctor.reg_patient_name.setText(f"演示患者{self.suffix}")
        self.click(reg_tab, "查询患者")
        for row in range(self.doctor.reg_patient_table.rowCount()):
            if self.doctor.reg_patient_table.item(row, 1).text() == f"演示患者{self.suffix}":
                self.doctor.reg_patient_table.selectRow(row)
                self.highlight(self.doctor.reg_patient_table)
                self.doctor._select_registration_patient(row, 0)
                break
        self.click(reg_tab, "刷新医生")
        self.set_combo(self.doctor.reg_doctor, f"演示医生{self.suffix}")
        self.click(reg_tab, "挂号")
        regs = self.cashier_api.call(
            "GET", "/registrations/", params={"patient_id": self.patient_id}
        )
        self.registration_id = regs[0]["id"]
        self.scene("✅ 医生站挂号成功，可直接接诊")

        self.scene("③ 护士窗口：分诊登记 → 叫号", self.nurse)
        nurse_tab = self.switch_inner(self.nurse, "分诊叫号")
        self.nurse.triage_reg_id.setValue(self.registration_id)
        self.click(nurse_tab, "登记分诊")
        self.click(nurse_tab, "刷新队列")
        for row in range(self.nurse.queue_table.rowCount()):
            if self.nurse.queue_table.item(row, 1).text() == str(self.registration_id):
                self.nurse.queue_table.selectRow(row)
                break
        self.click(nurse_tab, "叫号")
        self.scene("✅ 已分诊并叫号")

        self.scene("④ 医生窗口：接诊 → 病历 → 签名", self.doctor)
        reception = self.switch_inner(self.doctor, "接诊")
        self.click(reception, "刷新待接诊挂号")
        self.doctor.reg_id.setValue(self.registration_id)
        self.doctor.diagnosis.setText("急性上呼吸道感染")
        self.click(reception, "开始接诊")
        encounters = self.doctor_api.call(
            "GET", "/encounters/", params={"patient_id": self.patient_id}
        )
        self.encounter_id = encounters[0]["id"]
        record_tab = self.switch_inner(self.doctor, "病历")
        self.doctor.mr_encounter_id.setValue(self.encounter_id)
        self.doctor.record_edits["chief_complaint"].setPlainText("发热咳嗽 2 天")
        self.doctor.record_edits["present_illness"].setPlainText("受凉后发热，最高 38.5℃")
        self.doctor.record_edits["physical_exam"].setPlainText("咽充血，双肺呼吸音清")
        self.doctor.record_edits["treatment_advice"].setPlainText("抗感染，多饮水")
        self.click(record_tab, "保存 / 更新")
        self.click(record_tab, "签名锁定")
        record = self.doctor_api.call(
            "GET", f"/encounters/{self.encounter_id}/medical-record"
        )
        assert record.get("signed_by"), f"病历未签名：{record}"
        self.scene("✅ 接诊与病历签名完成")

        self.scene("⑤ 医生窗口：调阅历史诊疗（病历/处方/检验/治疗/收费）", self.doctor)
        history_tab = self.switch_inner(self.doctor, "历史诊疗")
        self.doctor.history_name.setText(f"演示患者{self.suffix}")
        self.click(history_tab, "查询患者")
        for row in range(self.doctor.history_patient_table.rowCount()):
            if self.doctor.history_patient_table.item(row, 1).text() == f"演示患者{self.suffix}":
                self.doctor.history_patient_table.selectRow(row)
                self.doctor._select_history_patient(row, 0)
                break
        assert self.doctor.history_enc_table.rowCount() >= 2, "历史就诊数不足"
        for row in range(self.doctor.history_enc_table.rowCount()):
            if self.doctor.history_enc_table.item(row, 0).text() == str(self.prior_encounter_id):
                self.doctor.history_enc_table.selectRow(row)
                self.doctor._history_select(row, 0)
                break
        assert "头晕 1 周" in self.doctor.history_record.toPlainText(), "历史病历未显示"
        assert self.doctor.history_rx_table.rowCount() >= 1, "历史处方未显示"
        assert self.doctor.history_lab_table.rowCount() >= 1, "历史检验未显示"
        assert self.doctor.history_treat_table.rowCount() >= 1, "历史治疗未显示"
        detail_tabs = self.doctor.history_detail_tabs
        for label in ("处方", "检验", "治疗", "收费", "支付"):
            for index in range(detail_tabs.count()):
                if detail_tabs.tabText(index) == label:
                    detail_tabs.setCurrentIndex(index)
                    self.caption.set_text(f"⑤ 历史诊疗 · {label}")
                    self.wait(1.3)
                    break
        self.scene("✅ 历史病历、处方、检验、治疗、收费均可调阅")

        self.scene("⑥ 医生窗口：开方 + 检验 + 治疗", self.doctor)
        rx_tab = self.switch_inner(self.doctor, "开方")
        self.doctor.rx_encounter_id.setValue(self.encounter_id)
        self.click(rx_tab, "刷新药品目录")
        for row in range(self.doctor.drug_table.rowCount()):
            if f"演示阿莫西林{self.suffix}" in self.doctor.drug_table.item(row, 1).text():
                self.doctor.drug_table.selectRow(row)
                self.doctor.rx_drug_id.setText(self.doctor.drug_table.item(row, 0).text())
                break
        self.doctor.rx_quantity.setValue(2)
        self.doctor.rx_dosage.setText("0.5g")
        self.doctor.rx_frequency.setText("tid")
        self.doctor.rx_route.setText("口服")
        self.click(rx_tab, "开方")
        exam_tab = self.switch_inner(self.doctor, "检验")
        self.doctor.exam_encounter_id.setValue(self.encounter_id)
        self.click(exam_tab, "刷新检验项目")
        self.set_combo(self.doctor.lab_combo, f"血常规{self.suffix}")
        self.click(exam_tab, "开检验单")
        treat_tab = self.switch_inner(self.doctor, "治疗")
        self.doctor.treat_encounter_id.setValue(self.encounter_id)
        self.click(treat_tab, "刷新治疗项目")
        self.set_combo(self.doctor.treat_combo, f"雾化治疗{self.suffix}")
        self.doctor.treat_quantity.setValue(1)
        self.click(treat_tab, "开治疗单")
        self.scene("✅ 处方、检验、治疗已开立")

        self.scene("⑦ 治疗室窗口：登记清创缝合处置", self.treatment)
        queue_tab = self.switch_inner(self.treatment, "治疗排队")
        self.treatment.patient_id.setValue(self.patient_id)
        self.treatment.encounter_id.setValue(self.encounter_id)
        self.set_combo(self.treatment.template, "清创缝合")
        self.treatment.procedure.setText("清创缝合")
        self.treatment.diagnosis.setText("右手掌裂伤")
        self.treatment.template_edits["site"].setText("右手掌")
        self.treatment.template_edits["size"].setText("3cm")
        self.click(queue_tab, "创建处置")
        treatment_cases = self.admin.call(
            "GET", "/treatment-room/cases", params={"status": "waiting"}
        )
        treatment_case = next(
            row for row in treatment_cases if row["encounter_id"] == self.encounter_id
        )
        for row in range(self.treatment.table.rowCount()):
            if self.treatment.table.item(row, 0).text() == treatment_case["case_no"]:
                self.treatment.table.selectRow(row)
                self.treatment._select_case(row, 0)
                break
        self.scene("✅ 已登记治疗室清创处置（费用进入本次就诊）")

        self.scene("⑧ 收费员窗口：收费", self.cashier)
        charge_tab = self.switch_inner(self.cashier, "收费")
        self.cashier.c_encounter_id.setValue(self.encounter_id)
        self.click(charge_tab, "查询费用")
        self.click(charge_tab, "收费")
        payments = self.cashier_api.call(
            "GET", "/payments/", params={"encounter_id": self.encounter_id}
        )
        assert payments and payments[0]["status"] == "paid"
        assert abs(payments[0]["amount"] - 185.0) < 0.01, payments[0]
        self.payment_id = payments[0]["id"]
        self.scene(f"✅ 收费完成：{payments[0]['amount']:.2f} 元")

        self.scene("⑨ 治疗室窗口：知情同意 → 开始 → 完成处置", self.treatment)
        handle_tab = self.switch_inner(self.treatment, "处置记录")
        self.treatment.consent.setChecked(True)
        self.treatment.consent_signer.setText(f"演示患者{self.suffix}")
        self.treatment.consent_relation.setText("本人")
        signature_file = str(ROOT / "docs" / "dept_preview" / "signature_demo.png")
        self.treatment.consent_signature_local = signature_file
        self.treatment.consent_signature_path.setText(signature_file)
        self.treatment.anesthesia.setText("利多卡因局麻")
        self.treatment.findings.setText("右手掌 3cm 裂伤")
        self.click(handle_tab, "开始")
        self.treatment.procedure_detail.setText("清创后 3-0 丝线缝合 3 针")
        self.treatment.sutures.setText("3-0 丝线 3 针")
        self.treatment.dressing.setText("无菌敷料包扎")
        self.click(handle_tab, "完成")
        case_detail = self.admin.call(
            "GET", f"/treatment-room/cases/{treatment_case['id']}"
        )
        assert case_detail["status"] == "completed", case_detail
        followups = self.admin.call(
            "GET", "/treatment-room/follow-ups", params={"status": "pending"}
        )
        assert any(row["case_id"] == treatment_case["id"] for row in followups)
        self.scene("✅ 处置完成，自动生成换药随访")

        self.scene("⑩ 库房窗口：药品收货入库", self.warehouse)
        inbound_tab = self.switch_inner(self.warehouse, "入库单")
        self.set_combo(self.warehouse.in_type, "药品")
        self.click(inbound_tab, "刷新供应商")
        self.set_combo(self.warehouse.in_supplier, f"演示供应商{self.suffix}")
        self.warehouse.in_drug_source.setCurrentIndex(1)
        self.click(inbound_tab, "刷新药品")
        self.set_combo(self.warehouse.in_drug, f"演示阿莫西林{self.suffix}")
        self.warehouse.in_batch.setText(f"WINDEMO-{self.suffix}")
        self.warehouse.in_expiry.setText(self.future)
        self.warehouse.in_qty.setValue(10)
        self.warehouse.in_price.setText("12.50")
        self.click(inbound_tab, "添加药品行")
        self.click(inbound_tab, "提交入库单")
        self.click(inbound_tab, "刷新入库单")
        orders = self.warehouse_api.call("GET", "/inbound/orders")
        order_no = orders[0]["order_no"]
        for row in range(self.warehouse.order_table.rowCount()):
            if self.warehouse.order_table.item(row, 0).text() == order_no:
                self.warehouse.order_table.selectRow(row)
                self.warehouse._select_order(row, 0)
                break
        self.click(inbound_tab, "全部合格验收")
        self.click(inbound_tab, "入库")
        stock = self.warehouse_api.call(
            "GET", f"/warehouse/stocks?drug_id={self.drug['id']}"
        )
        assert sum(row["quantity"] for row in stock) == 10
        self.scene("✅ 入库完成，总库 10 盒")

        self.scene("⑪ 药房窗口：向库房申请领用", self.pharmacy)
        out_tab = self.switch_inner(self.pharmacy, "领用出库")
        self.click(out_tab, "刷新药品")
        self.set_combo(self.pharmacy.out_drug, f"演示阿莫西林{self.suffix}")
        self.pharmacy.out_batch.setText(f"WINDEMO-{self.suffix}")
        self.pharmacy.out_qty.setValue(2)
        self.click(out_tab, "添加药品行")
        self.click(out_tab, "提交领用申请")
        self.scene("✅ 领用申请已提交")

        self.scene("⑫ 库房窗口：审核并出库给药房", self.warehouse)
        handle_tab = self.switch_inner(self.warehouse, "出库处理")
        self.click(handle_tab, "刷新出库单")
        pendings = self.warehouse_api.call(
            "GET", "/warehouse/outbound-orders?status=submitted"
        )
        target_no = pendings[0]["outbound_no"]
        for row in range(self.warehouse.handle_table.rowCount()):
            if self.warehouse.handle_table.item(row, 0).text() == target_no:
                self.warehouse.handle_table.selectRow(row)
                self.warehouse._select_handle_order(row, 0)
                break
        self.click(handle_tab, "审核通过")
        self.click(handle_tab, "全部出库")
        stock = self.pharmacist_api.call(
            "GET", f"/pharmacy/stocks?drug_id={self.drug['id']}"
        )
        assert sum(row["quantity"] for row in stock) == 2
        self.scene("✅ 出库完成，药房库存 2 盒")

        self.scene("⑬ 药房窗口：取药码核对 → 叫号 → 签字发药", self.pharmacy)
        disp_tab = self.switch_inner(self.pharmacy, "发药")
        self.pharmacy._load_worklist()
        target_index = next(
            (
                index
                for index, row in enumerate(self.pharmacy.worklist)
                if row["encounter_id"] == self.encounter_id
            ),
            -1,
        )
        assert target_index >= 0, "待发药队列没有本次就诊"
        self.pharmacy.worklist_table.selectRow(target_index)
        self.pharmacy._select_worklist(target_index, 0)
        self.click(disp_tab, "核对取药码")
        self.pharmacy.receiver_name.setText("演示患者本人")
        self.click(disp_tab, "叫号")
        self.click(disp_tab, "核对发药")
        self.click(disp_tab, "退药（库存回补）")
        remaining = self.pharmacist_api.call("GET", "/pharmacy/worklist")
        assert all(row["encounter_id"] != self.encounter_id for row in remaining)
        self.scene("✅ 取药码核对、发药、退药完成")

        self.scene("⑭ 收费员窗口：发票作废 → 整单退费", self.cashier)
        print_tab = self.switch_inner(self.cashier, "打印")
        self.cashier.pr_payment_id.setValue(self.payment_id)
        self.cashier.void_reason.setText("演示：发票作废重打")
        self.click(print_tab, "作废发票")
        invoice = self.cashier_api.call("GET", f"/payments/{self.payment_id}")
        assert invoice["invoice_status"] == "void", invoice
        charge_tab = self.switch_inner(self.cashier, "收费")
        self.cashier.refund_payment_id.setValue(self.payment_id)
        self.click(charge_tab, "加载收费明细")
        self.click(charge_tab, "全部退")
        refunded = self.cashier_api.call("GET", f"/payments/{self.payment_id}")
        assert refunded["status"] == "refunded", refunded
        self.scene("✅ 发票已作废，收费已整单退费")

        self.scene("⑮ 收费员窗口：开班与日结", self.cashier)
        shift_tab = self.switch_inner(self.cashier, "交班")
        daily = self.cashier_api.call("GET", "/cashier/daily")
        if not any(row.get("status") == "open" for row in daily["shifts"]):
            self.cashier.opening_float.setValue(100)
            self.click(shift_tab, "开班")
            daily = self.cashier_api.call("GET", "/cashier/daily")
        assert daily["shifts"], "交班记录未生成"
        self.scene("✅ 收费员开班，日结可见交班记录")

        self.scene("⑯ 检验科窗口：采样 → 签收 → 检验 → 报告 → 审核", self.lab)
        lab_tab = self.switch_inner(self.lab, "检验工作台")
        lab_id = self.select_lab_row()
        self.click(lab_tab, "采样")
        lab_id = self.select_lab_row()
        self.click(lab_tab, "签收")
        lab_id = self.select_lab_row()
        self.click(lab_tab, "开始检验")
        lab_id = self.select_lab_row()
        self.lab.result_text.setText("白细胞 6.2×10^9/L，中性粒细胞 62%")
        self.click(lab_tab, "出具报告")
        lab_id = self.select_lab_row()
        self.click(lab_tab, "审核报告")
        reviewed = self.lab_api.call("GET", f"/lab/requests/{lab_id}")
        assert reviewed["status"] in ("reported", "reviewed"), reviewed
        self.lab._refresh_reviewed()
        assert self.lab.reviewed_table.rowCount() >= 1
        self.scene("✅ 检验采样、签收、报告、审核完成")

        self.scene("演示完成：挂号 → 医生 → 治疗室 → 收费 → 发票/退费 → 库房 → 药房 → 交班 → 检验")
        self.tile_windows()
        self.wait(2.5)
        self.capture_timer.stop()
        self.capture()
        self.success = True


    def select_lab_row(self) -> int:
        self.lab._refresh()
        for row in range(self.lab.table.rowCount()):
            if (
                self.lab.table.item(row, 2).text() == f"演示患者{self.suffix}"
                and "血常规" in self.lab.table.item(row, 3).text()
            ):
                self.lab.table.selectRow(row)
                self.lab._select_row(row, 0)
                return int(self.lab.table.item(row, 0).text())
        raise RuntimeError("检验工作列表没有本次申请")

    def start(self) -> None:
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.capture_timer.start(200)
            self.wait(0.5)
            self.setup()
            self.run_flow()
        except Exception as exc:  # noqa: BLE001
            print(f"演示异常：{exc}", flush=True)
            self.caption.set_text(f"❌ 演示中断：{exc}")
            self.capture()
            self.capture_timer.stop()
            self.success = False
            self.error = str(exc)
        finally:
            for window in self.windows.values():
                window.close()
            self.caption.close()
            QApplication.instance().quit()


def encode_video() -> bool:
    frames = sorted(FRAME_DIR.glob("frame_*.jpg"))
    if len(frames) < 3:
        print("帧数不足，无法生成录像")
        return False
    VIDEO_PATH.unlink(missing_ok=True)
    result = subprocess.run(
        [
            FFMPEG, "-y", "-framerate", "5",
            "-i", str(FRAME_DIR / "frame_%04d.jpg"),
            "-vf", "scale=1600:900:force_original_aspect_ratio=decrease,"
                   "pad=1600:900:(ow-iw)/2:(oh-ih)/2:color=0x0f172a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
            str(VIDEO_PATH),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not VIDEO_PATH.is_file():
        print("ffmpeg 生成录像失败")
        return False
    print(f"操作录像已生成：{VIDEO_PATH}（{len(frames)} 帧）")
    return True


def main() -> int:
    app = QApplication(sys.argv)
    controller = DemoController()
    controller.tile_windows()
    QTimer.singleShot(500, controller.start)
    app.exec()
    ok = encode_video()
    print("演示结果：", "通过" if controller.success else f"失败 {getattr(controller, 'error', '')}")
    return 0 if ok and controller.success else 1


if __name__ == "__main__":
    raise SystemExit(main())



