"""界面操作演示录像：真实驱动客户端控件完成挂号→接诊→收费→入库→领用→发药→退药。

运行：
    .venv\\Scripts\\python.exe scripts\\record_ui_demo.py
产出：
    docs/全流程操作录像.mp4
"""
import base64
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtCore import QPoint
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
from his_client.ui.nurse import NurseWidget  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "ui_demo_frames"
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


def click_button(container: QWidget, text: str) -> None:
    for button in container.findChildren(QPushButton):
        if button.text().strip() == text and button.isVisible():
            QTest.mouseClick(button, Qt.LeftButton)
            return
    raise RuntimeError(f"找不到按钮：{text}")


def find_combo(container: QWidget, predicate) -> QComboBox | None:
    for combo in container.findChildren(QComboBox):
        if combo.isVisible() and predicate(combo):
            return combo
    return None


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HIS 全流程操作演示（真实客户端界面）")
        self.resize(1480, 940)
        self.frame_index = 0
        self.point: QPoint | None = None
        self.point_until = 0.0

        self.admin = Api("admin", "admin123")
        self.cashier_api = Api("cashier", "cashier123")
        self.doctor_api = Api("doctor", "doctor123")
        self.nurse_api = Api("nurse", "nurse123")
        self.pharmacist_api = Api("pharmacist", "pharm123")
        self.warehouse_api = Api("warehouse", "warehouse123")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 12, 14, 12)
        self.caption = QLabel("准备开始…")
        self.caption.setStyleSheet(
            "font-size:19px;font-weight:bold;color:#0f172a;background:#e0f2fe;"
            "border:1px solid #7dd3fc;border-radius:6px;padding:10px"
        )
        self.caption.setWordWrap(True)
        layout.addWidget(self.caption)

        self.tabs = QTabWidget()
        self.warehouse = PharmacyWidget(
            ApiClient(BASE, "warehouse", "warehouse123"), role="warehouse"
        )
        self.cashier = CashierWidget(ApiClient(BASE, "cashier", "cashier123"))
        self.nurse = NurseWidget(ApiClient(BASE, "nurse", "nurse123"))
        self.doctor = DoctorWidget(ApiClient(BASE, "doctor", "doctor123"))
        self.pharmacy = PharmacyWidget(
            ApiClient(BASE, "pharmacist", "pharm123"), role="pharmacist"
        )
        self.tabs.addTab(self.warehouse, "库房工作站")
        self.tabs.addTab(self.cashier, "收费员工作站")
        self.tabs.addTab(self.nurse, "护士工作站")
        self.tabs.addTab(self.doctor, "医生工作站")
        self.tabs.addTab(self.pharmacy, "药房工作站")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.frames: list[Path] = []
        self.capture_timer = QTimer(self)
        self.capture_timer.timeout.connect(self.capture)

        self.suffix = datetime.now().strftime("%m%d%H%M%S")
        self.patient_id = None
        self.registration_id = None
        self.encounter_id = None
        self.payment_id = None
        self.outbound_id = None
        self.dispense_id = None

    # ---------- 基础操作 ----------
    def wait(self, seconds: float = 0.7) -> None:
        QTest.qWait(int(seconds * 1000))

    def scene(self, text: str) -> None:
        self.caption.setText(text)
        self.wait(1.0)

    def switch_role(self, widget: QWidget) -> None:
        self.tabs.setCurrentWidget(widget)
        self.wait(0.5)

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
            self.point = widget.mapTo(self, widget.rect().center())
            self.point_until = time.time() + 0.9
        except Exception:
            self.point = None

    def click(self, container: QWidget, text: str) -> None:
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
        if not self.frames:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.png"):
                old.unlink()
        pixmap = self.grab()
        if self.point is not None and time.time() < self.point_until:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor("#ef4444"), 3))
            painter.setBrush(QColor(239, 68, 68, 70))
            painter.drawEllipse(self.point, 16, 16)
            painter.setBrush(QColor("#ef4444"))
            triangle = QPolygonF(
                [
                    QPoint(self.point.x() + 10, self.point.y()),
                    QPoint(self.point.x() + 24, self.point.y() + 6),
                    QPoint(self.point.x() + 12, self.point.y() + 16),
                ]
            )
            painter.drawPolygon(triangle)
            painter.end()
        self.frame_index += 1
        path = FRAME_DIR / f"frame_{self.frame_index:04d}.png"
        pixmap.save(str(path))
        self.frames.append(path)

    # ---------- 数据准备（镜头外） ----------
    def setup(self) -> None:
        future = (date.today() + timedelta(days=900)).isoformat()
        self.future = future
        self.supplier = self.admin.call(
            "POST", "/suppliers/",
            json={"code": f"UIDEMO-SUP-{self.suffix}", "name": f"演示供应商{self.suffix}"},
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
            json={"code": f"DEMOLAB{self.suffix[-6:]}", "name": f"血常规{self.suffix}", "price": 20.0},
        )
        self.treat_item = self.admin.call(
            "POST", "/charges/items/",
            json={
                "code": f"UIDEMO-TRT-{self.suffix}",
                "name": f"雾化治疗{self.suffix}",
                "category": "treatment",
                "price": 30.0,
                "insurance_ratio": 0.0,
            },
        )

    # ---------- 演流程 ----------
    def run_flow(self) -> None:
        try:
            self.scene("① 库房工作站：药品收货入库（收货→验收→入库）")
            self.switch_role(self.warehouse)
            inbound_tab = self.switch_inner(self.warehouse, "入库单")
            self.set_combo(self.warehouse.in_type, "药品")
            self.click(inbound_tab, "刷新供应商")
            self.set_combo(self.warehouse.in_supplier, f"演示供应商{self.suffix}")
            self.warehouse.in_drug_source.setCurrentIndex(1)  # 本店药品
            self.click(inbound_tab, "刷新药品")
            self.set_combo(self.warehouse.in_drug, f"演示阿莫西林{self.suffix}")
            self.warehouse.in_batch.setText(f"UIDEMO-{self.suffix}")
            self.warehouse.in_expiry.setText(self.future)
            self.warehouse.in_qty.setValue(10)
            self.warehouse.in_price.setText("12.50")
            self.highlight(self.warehouse.in_price)
            self.click(inbound_tab, "添加药品行")
            self.click(inbound_tab, "提交入库单")
            self.click(inbound_tab, "刷新入库单")
            orders = self.warehouse_api.call("GET", "/inbound/orders")
            order = orders[0]
            self.select_table_row(self.warehouse.order_table, order["order_no"], 0)
            self.warehouse._select_order(0, 0)
            self.wait(0.4)
            self.click(inbound_tab, "全部合格验收")
            self.click(inbound_tab, "入库")
            stock = self.warehouse_api.call(
                "GET", f"/warehouse/stocks?drug_id={self.drug['id']}"
            )
            assert sum(row["quantity"] for row in stock) == 10, f"入库失败：{stock}"
            self.scene("✅ 入库完成：总库 10 盒")

            self.scene("② 收费员工作站：患者建档 + 现场挂号")
            self.switch_role(self.cashier)
            patient_tab = self.switch_inner(self.cashier, "患者建档")
            self.cashier.p_name.setText(f"演示患者{self.suffix}")
            self.cashier.p_id_number.setText(f"1101011995{self.suffix[-8:]}")
            self.cashier.p_phone.setText("13800000000")
            self.click(patient_tab, "建档")
            patients = self.cashier_api.call(
                "GET", "/patients/", params={"id_number": f"1101011995{self.suffix[-8:]}"}
            )
            self.patient_id = patients[0]["id"]
            reg_tab = self.switch_inner(self.cashier, "挂号")
            self.cashier.r_patient_id.setValue(self.patient_id)
            self.click(reg_tab, "刷新医生列表")
            for row in range(self.cashier.r_doctor_list.rowCount()):
                if f"演示医生{self.suffix}" in self.cashier.r_doctor_list.item(row, 1).text():
                    self.cashier.r_doctor_list.selectRow(row)
                    self.highlight(self.cashier.r_doctor_list)
                    self.cashier._pick_doctor(row, 0)
                    break
            self.click(reg_tab, "挂号")
            regs = self.cashier_api.call(
                "GET", "/registrations/", params={"patient_id": self.patient_id}
            )
            self.registration_id = regs[0]["id"]
            assert regs[0]["status"] == "registered"
            self.scene("✅ 建档+挂号完成")

            self.scene("③ 护士工作站：分诊登记 → 叫号")
            self.switch_role(self.nurse)
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

            self.scene("④ 医生工作站：接诊 → 病历 → 签名")
            self.switch_role(self.doctor)
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

            self.scene("⑤ 医生工作站：开方（阿莫西林 2 盒）+ 检验 + 治疗")
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

            self.scene("⑥ 收费员工作站：收费（医保结算 + 现金）")
            self.switch_role(self.cashier)
            charge_tab = self.switch_inner(self.cashier, "收费")
            self.cashier.c_encounter_id.setValue(self.encounter_id)
            self.click(charge_tab, "查询费用")
            self.click(charge_tab, "收费")
            payments = self.cashier_api.call(
                "GET", "/payments/", params={"encounter_id": self.encounter_id}
            )
            self.payment_id = payments[0]["id"]
            assert payments[0]["status"] == "paid"
            self.scene(f"✅ 收费完成：{payments[0]['amount']:.2f} 元")

            self.scene("⑦ 药房工作站：向库房申请领用阿莫西林")
            self.switch_role(self.pharmacy)
            out_tab = self.switch_inner(self.pharmacy, "领用出库")
            self.click(out_tab, "刷新药品")
            self.set_combo(self.pharmacy.out_drug, f"演示阿莫西林{self.suffix}")
            self.pharmacy.out_batch.setText(f"UIDEMO-{self.suffix}")
            self.pharmacy.out_qty.setValue(2)
            self.click(out_tab, "添加药品行")
            self.click(out_tab, "提交领用申请")
            self.scene("✅ 领用申请已提交，等待库房审核")

            self.scene("⑧ 库房工作站：审核领用 → 出库给药房")
            self.switch_role(self.warehouse)
            handle_tab = self.switch_inner(self.warehouse, "出库处理")
            self.click(handle_tab, "刷新出库单")
            pendings = self.warehouse_api.call("GET", "/warehouse/outbound-orders?status=submitted")
            self.outbound_id = pendings[0]["id"]
            for row in range(self.warehouse.handle_table.rowCount()):
                if self.warehouse.handle_table.item(row, 2).text() == "已申请":
                    self.warehouse.handle_table.selectRow(row)
                    self.highlight(self.warehouse.handle_table)
                    self.warehouse._select_handle_order(row, 0)
                    break
            self.click(handle_tab, "审核通过")
            self.click(handle_tab, "全部出库")
            stock = self.pharmacist_api.call(
                "GET", f"/pharmacy/stocks?drug_id={self.drug['id']}"
            )
            assert sum(row["quantity"] for row in stock) == 2, f"药房未收到药：{stock}"
            self.scene("✅ 库房出库完成，药房库存 2 盒")

            self.scene("⑨ 药房工作站：发药 → 退药（库存回补）")
            self.switch_role(self.pharmacy)
            disp_tab = self.switch_inner(self.pharmacy, "发药")
            self.pharmacy.disp_encounter_id.setValue(self.encounter_id)
            self.click(disp_tab, "发药")
            self.click(disp_tab, "退药（库存回补）")
            self.scene("✅ 发药/退药完成，库存已回补")

            self.scene("⑩ 演示完成：挂号→接诊→收费→领用→出库→发药→退药 全流程贯通")
            self.wait(2.0)
            self.capture_timer.stop()
            self.capture()
            self.close()
            QApplication.instance().quit()
            self.success = True
        except Exception as exc:  # noqa: BLE001
            self.caption.setText(f"❌ 演示中断：{exc}")
            self.capture()
            self.capture_timer.stop()
            self.close()
            QApplication.instance().quit()
            self.success = False
            self.error = str(exc)

    def select_table_row(self, table: QTableWidget, value: str, column: int) -> None:
        for row in range(table.rowCount()):
            item = table.item(row, column)
            if item and item.text() == value:
                table.selectRow(row)
                self.highlight(table)
                return
        raise RuntimeError(f"表格找不到：{value}")

    def start(self) -> None:
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.png"):
                old.unlink()
            self.capture_timer.start(120)
            self.wait(0.5)
            self.setup()
            self.run_flow()
        except Exception as exc:  # noqa: BLE001
            print(f"演示异常：{exc}", flush=True)
            self.caption.setText(f"❌ 演示中断：{exc}")
            self.capture()
            self.capture_timer.stop()
            self.success = False
            self.error = str(exc)
            self.close()
            QApplication.instance().quit()


def encode_video() -> bool:
    frames = sorted(FRAME_DIR.glob("frame_*.png"))
    if len(frames) < 3:
        print("帧数不足，无法生成录像")
        return False
    VIDEO_PATH.unlink(missing_ok=True)
    result = subprocess.run(
        [
            FFMPEG,
            "-y",
            "-framerate",
            "8",
            "-i",
            str(FRAME_DIR / "frame_%04d.png"),
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x0f172a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
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
    window = DemoWindow()
    window.show()
    QTimer.singleShot(300, window.start)
    app.exec()
    ok = encode_video()
    print("演示结果：", "通过" if getattr(window, "success", False) else f"失败 {getattr(window, 'error', '')}")
    return 0 if ok and getattr(window, "success", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
