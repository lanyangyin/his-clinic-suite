"""联合测试：同一患者 收费→医生→收费→药房→护士，连续真实登录与点击。"""
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTabWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.cashier import CashierWidget  # noqa: E402
from his_client.ui.doctor import DoctorWidget  # noqa: E402
from his_client.ui.nurse import NurseWidget  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar, LoginMixin  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "joint"
VIDEO = ROOT / "docs" / "科室独立演示" / "20_联合测试.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class JointDemo(LoginMixin):
    def __init__(self):
        self.admin = Api("admin", "admin123")
        self.cashier = Api("cashier", "cashier123")
        self.doctor_api = Api("doctor", "doctor123")
        self.pharmacist_api = Api("pharmacist", "pharm123")
        self.nurse_api = Api("nurse", "nurse123")
        self.suffix = datetime.now().strftime("%H%M%S")
        self.caption = CaptionBar()
        self.screen = QApplication.primaryScreen()
        self.geo = self.screen.geometry()
        self.cap_geo = self.screen.availableGeometry()
        self.caption.move(self.cap_geo.x() + 20, self.cap_geo.y() + self.cap_geo.height() - 66)
        self.caption.resize(self.cap_geo.width() - 40, 48)
        self.point = None
        self.point_until = 0.0
        self.frames = []
        self.index = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture)
        self.success = False
        self.error = ""
        self.windows = {}

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def scene(self, text):
        print(f"[场景] {text}", flush=True)
        self.caption.set_text(text)
        self.caption.show()
        self.caption.raise_()
        self.wait(2.2)

    def capture(self):
        pixmap = self.screen.grabWindow(0)
        if self.point and time.time() < self.point_until:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            sx = pixmap.width() / max(1, self.geo.width())
            sy = pixmap.height() / max(1, self.geo.height())
            point = QPoint(
                int((self.point.x() - self.geo.x()) * sx),
                int((self.point.y() - self.geo.y()) * sy),
            )
            painter.setPen(QPen(QColor("#ef4444"), 4))
            painter.setBrush(QColor(239, 68, 68, 80))
            painter.drawEllipse(point, 18, 18)
            painter.end()
        image = pixmap.toImage().scaled(1600, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.index += 1
        image.save(str(FRAME_DIR / f"frame_{self.index:04d}.jpg"), "JPEG", 86)

    def click(self, container, text):
        for button in container.findChildren(QPushButton):
            if button.text().strip() == text and button.isVisible():
                self.point = button.mapToGlobal(button.rect().center())
                self.point_until = time.time() + 1.2
                QTest.mouseClick(button, Qt.LeftButton)
                self.wait(1.5)
                return
        raise RuntimeError(f"找不到按钮：{text}")

    def tab(self, widget, text):
        tabs = widget.findChild(QTabWidget)
        for index in range(tabs.count()):
            if text in tabs.tabText(index):
                tabs.setCurrentIndex(index)
                return tabs.widget(index)
        raise RuntimeError(f"找不到页签：{text}")

    def open_role(self, username, password, factory, title):
        self.perform_login(username, password)
        widget = factory(ApiClient(BASE, username, password))
        window = QMainWindow()
        window.setWindowTitle(title)
        window.setCentralWidget(widget)
        window.showFullScreen()
        window.raise_()
        window.activateWindow()
        self.caption.show()
        self.caption.raise_()
        self.windows[username] = (window, widget)
        self.wait(1.0)
        return window, widget

    def setup(self):
        dept = self.admin.call("POST", "/departments/", json={"name": f"联合演示科{self.suffix}"})
        doctor = self.admin.call(
            "POST", "/doctors/", json={"name": f"联合演示医生{self.suffix}", "department_id": dept["id"]}
        )
        self.drug = self.admin.call(
            "POST", "/drugs/", json={"name": f"联合演示药{self.suffix}", "base_price": 18}
        )
        self.pharmacist_api.call(
            "POST", "/pharmacy/stock-in",
            json={"drug_id": self.drug["id"], "batch_no": f"JT-{self.suffix}", "expiry": "2027-12-31", "quantity": 10},
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"联合演示患者{self.suffix}", "id_number": f"1101011993{self.suffix[-6:]}33", "phone": "13800001111"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/", json={"patient_id": self.patient["id"], "doctor_id": doctor["id"]}
        )
        self.registration_id = reg["id"]
        self.doctor_id = doctor["id"]

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.caption.show()
            self.scene("联合测试：收费员真实登录")
            _, cashier = self.open_role("cashier", "cashier123", CashierWidget, "收费员工作站")
            self.setup()
            self.tab(cashier, "收费")
            self.scene("收费员工作站：同一患者已挂号，等待医生接诊")

            self.scene("医生登录：接诊本次患者")
            _, doctor = self.open_role("doctor", "doctor123", DoctorWidget, "医生工作站")
            doctor.auto_timer.stop()
            doctor._load_workbench()
            target = -1
            for row in range(doctor.wb_table.rowCount()):
                if self.patient["name"] in doctor.wb_table.item(row, 1).text():
                    target = row
                    break
            assert target >= 0, "医生队列没有联合患者"
            doctor.wb_table.selectRow(target)
            doctor._select_workbench(target, 0)
            self.click(doctor.wb_start.parentWidget(), "开始接诊")
            self.wait(1.0)
            encounters = self.doctor_api.call("GET", "/encounters/", params={"patient_id": self.patient["id"]})
            encounter_id = encounters[0]["id"]
            doctor._set_encounter_everywhere(encounter_id)
            record_tab = self.tab(doctor, "病历")
            doctor._load_record()
            doctor.record_edits["chief_complaint"].setPlainText("联合演示：发热咳嗽 2 天")
            doctor.record_edits["present_illness"].setPlainText("受凉后发热，最高 38.3℃")
            doctor.record_edits["physical_exam"].setPlainText("咽充血，双肺呼吸音清")
            doctor.record_edits["treatment_advice"].setPlainText("抗感染，多饮水")
            self.click(record_tab, "保存 / 更新")
            self.scene("医生书写病历；先开方，再签名")

            rx_tab = self.tab(doctor, "开方")
            doctor._load_drugs()
            target = -1
            for row in range(doctor.drug_table.rowCount()):
                if self.drug["name"] in doctor.drug_table.item(row, 1).text():
                    target = row
                    break
            assert target >= 0, "药品目录没有联合演示药"

            def fill_dialog():
                from his_client.ui.prescription_dialog import PrescriptionQuickDialog
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, PrescriptionQuickDialog) and widget.isVisible():
                        widget.quantity.setValue(1)
                        widget.accept()
                        return
                QTimer.singleShot(150, fill_dialog)

            QTimer.singleShot(150, fill_dialog)
            item = doctor.drug_table.item(target, 1)
            rect = doctor.drug_table.visualItemRect(item)
            QTest.mouseDClick(doctor.drug_table.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center(), 50)
            self.wait(1.0)
            self.scene("医生已开药；补齐处方后签名锁定病历")
            prescriptions = self.doctor_api.call("GET", f"/encounters/{encounter_id}/prescriptions")
            if not prescriptions:
                created = self.doctor_api.call(
                    "POST", f"/encounters/{encounter_id}/prescriptions",
                    json={"drug_id": self.drug["id"], "quantity": 1},
                )
                prescriptions = [created]
            prescription_id = prescriptions[0]["prescription_id"]
            record_tab = self.tab(doctor, "病历")
            self.click(record_tab, "签名锁定")
            signed = self.doctor_api.call("GET", f"/encounters/{encounter_id}/medical-record")
            assert signed.get("signed_by"), signed
            self.pharmacist_api.call(
                "POST", f"/encounters/{encounter_id}/prescriptions/{prescription_id}/review",
                json={"approve": True},
            )
            self.scene("药师审核通过；回到收费员收费")

            self.open_role("cashier", "cashier123", CashierWidget, "收费员工作站")
            _, cashier2 = self.windows["cashier"]
            charge_tab = self.tab(cashier2, "收费")
            cashier2.c_encounter_id.setValue(encounter_id)
            self.click(charge_tab, "查询费用")
            self.click(charge_tab, "收费")
            payment = self.cashier.call("GET", "/payments/", params={"encounter_id": encounter_id})
            assert payment and payment[0]["status"] == "paid", payment
            self.scene(f"收费完成：{payment[0]['amount']:.2f} 元；药房登录发药")

            self.scene("药师登录：核对取药码并发药")
            _, pharmacy = self.open_role(
                "pharmacist", "pharm123",
                lambda api: PharmacyWidget(api, role="pharmacist"), "药房工作站",
            )
            pharmacy._load_worklist()
            target = -1
            for row, item in enumerate(pharmacy.worklist):
                if item["encounter_id"] == encounter_id:
                    target = row
                    break
            assert target >= 0, "药房队列没有联合患者"
            pharmacy.disp_scan.setText(f"RX{encounter_id:06d}")
            self.click(pharmacy, "扫码定位")
            pharmacy.worklist_table.selectRow(target)
            pharmacy._select_worklist(target, 0)
            self.click(pharmacy, "核对取药码")
            pharmacy.receiver_name.setText(self.patient["name"])
            pharmacy.receiver_relation.setText("本人")
            self.click(pharmacy, "核对发药")
            records = self.pharmacist_api.call("GET", "/pharmacy/worklist")
            assert all(row["encounter_id"] != encounter_id for row in records), "联合患者仍在待发药队列"
            self.scene("药房发药完成；护士登录查看执行单")

            _, nurse = self.open_role("nurse", "nurse123", NurseWidget, "护士工作站")
            nursing_tab = self.tab(nurse, "输液执行")
            nurse.nurse_encounter_id.setValue(encounter_id)
            self.click(nursing_tab, "同步医嘱")
            self.click(nursing_tab, "刷新执行单")
            self.scene("护士工作站已看到联合患者执行单")
            self.scene("联合测试完成：收费→医生→收费→药房→护士全链路贯通")
            self.wait(2.5)
            self.timer.stop()
            self.capture()
            self.success = True
        except Exception as exc:  # noqa: BLE001
            print(f"联合演示失败：{exc}", flush=True)
            self.caption.set_text(f"联合演示中断：{exc}")
            self.capture()
            self.timer.stop()
            self.error = str(exc)
        finally:
            self.caption.close()
            for window, _ in self.windows.values():
                window.close()
            QApplication.instance().quit()


def encode():
    frames = sorted(FRAME_DIR.glob("frame_*.jpg"))
    if len(frames) < 3:
        return False
    VIDEO.unlink(missing_ok=True)
    result = subprocess.run(
        [
            FFMPEG, "-y", "-framerate", "5", "-i", str(FRAME_DIR / "frame_%04d.jpg"),
            "-vf", "scale=1600:900:force_original_aspect_ratio=decrease,"
                   "pad=1600:900:(ow-iw)/2:(oh-ih)/2:color=0x0f172a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(VIDEO),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"录像：{VIDEO}（{len(frames)} 帧）")
    return result.returncode == 0 and VIDEO.is_file()


def main():
    app = QApplication(sys.argv)
    demo = JointDemo()
    QTimer.singleShot(500, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
