"""挂号收费科独立全流程慢速演示。

覆盖：患者建档 → 现场挂号 → 医生接诊后收费 → 重复收费报错
      → 发票作废 → 整单退费 → 开班/日结。
产出：docs/科室独立演示/01_挂号收费.mp4
"""
import json
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.cashier import CashierWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "cashier"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "01_挂号收费.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class CashierDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("挂号收费科 · cashier")
        self.widget = CashierWidget(ApiClient(BASE, "cashier", "cashier123"))
        self.setCentralWidget(self.widget)
        self.caption = CaptionBar()
        self.screen = QApplication.primaryScreen()
        self.geo = self.screen.geometry()
        self.cap_geo = self.screen.availableGeometry()
        self.caption.move(self.cap_geo.x() + 20, self.cap_geo.y() + 34)
        self.caption.resize(self.cap_geo.width() - 40, 48)
        self.frames: list[Path] = []
        self.index = 0
        self.point = None
        self.point_until = 0.0
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture)
        self.success = False
        self.error = ""
        self.admin = Api("admin", "admin123")
        self.cashier = Api("cashier", "cashier123")
        self.doctor = Api("doctor", "doctor123")
        self.suffix = datetime.now().strftime("%H%M%S")

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def scene(self, text, tab: QWidget | None = None):
        print(f"[场景] {text}", flush=True)
        if tab is not None:
            tabs = self.widget.findChild(__import__("PySide6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
            tabs.setCurrentWidget(tab)
        self.caption.set_text(text)
        self.caption.show()
        self.caption.raise_()
        self.wait(2.6)

    def tab(self, text):
        tabs = self.widget.findChild(__import__("PySide6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
        for index in range(tabs.count()):
            if text in tabs.tabText(index):
                tabs.setCurrentIndex(index)
                return tabs.widget(index)
        raise RuntimeError(f"找不到页签：{text}")

    def click(self, container, text):
        from PySide6.QtWidgets import QPushButton

        for button in container.findChildren(QPushButton):
            if button.text().strip() == text and button.isVisible():
                self.point = button.mapToGlobal(button.rect().center())
                self.point_until = time.time() + 1.2
                QTest.mouseClick(button, Qt.LeftButton)
                self.wait(1.8)
                return
        raise RuntimeError(f"找不到按钮：{text}")

    def capture(self):
        pixmap = self.screen.grabWindow(0)
        if self.point and time.time() < self.point_until:
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
            painter.end()
        image = pixmap.toImage().scaled(1600, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.index += 1
        path = FRAME_DIR / f"frame_{self.index:04d}.jpg"
        image.save(str(path), "JPEG", 86)
        self.frames.append(path)

    def setup(self):
        self.dept = self.admin.call("POST", "/departments/", json={"name": f"演示收费科{self.suffix}"})
        self.doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"演示收费医生{self.suffix}", "department_id": self.dept["id"]}
        )
        self.drug = self.admin.call(
            "POST", "/drugs/", json={"name": f"演示收费药{self.suffix}", "base_price": 18}
        )
        self.admin.call(
            "POST", "/invoices/batches",
            json={"prefix": f"CF{self.suffix[-4:]}", "start_no": 1, "end_no": 10, "assigned_to": "cashier"},
        )

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.showMaximized()
            self.caption.show()
            self.wait(1.2)
            self.setup()
            self.scene("快速挂号：只填姓名/性别/电话", self.tab("挂号"))
            reg_tab = self.tab("挂号")
            self.click(reg_tab, "刷新医生列表")
            self.widget._pick_doctor(0, 0)
            self.widget.qr_name.setText(f"快速患者{self.suffix}")
            self.widget.qr_gender.setCurrentIndex(1)
            self.widget.qr_phone.setText("13800005678")
            self.click(reg_tab, "快速建档并挂号")
            assert "快速挂号成功" in self.widget.reg_msg.text(), self.widget.reg_msg.text()
            self.scene(self.widget.reg_msg.text())
            self.scene("再演示完整 P0 建档与 NFC 发卡")
            patient_tab = self.tab("患者建档")
            self.widget.p_name.setText(f"收费演示患者{self.suffix}")
            self.widget.p_gender.setCurrentIndex(self.widget.p_gender.findData("male"))
            self.widget.p_id_number.setText(f"1101011997{self.suffix[-6:]}88")
            self.widget.p_birth_date.setText("1997-05-20")
            self.widget.p_phone.setText("13800001234")
            self.widget.p_address.setText("北京市东城区演示街道 1 号")
            self.widget.p_special_history.setText("2型糖尿病 8 年；高血压 5 年")
            self.widget.p_emergency_name.setText("演示家属")
            self.widget.p_emergency_relation.setText("配偶")
            self.widget.p_emergency_phone.setText("13900001234")
            self.widget.p_allergy_status.setCurrentIndex(self.widget.p_allergy_status.findData("none"))
            self.widget.p_privacy.setChecked(True)
            self.click(patient_tab, "建档")
            found = self.cashier.call(
                "GET", "/patients/", params={"name": f"收费演示患者{self.suffix}"}
            )
            patient = found[0]
            self.scene("患者建档完成，绑定 NFC 就诊卡")
            self.widget.q_name.setText(patient["name"])
            self.click(patient_tab, "查询")
            self.widget.patient_table.selectRow(0)
            self.widget._select_patient_row(0, 0)
            card_uid = f"NFC-DEMO-{self.suffix}"
            self.widget.p_card_uid.setText(card_uid)
            self.click(patient_tab, "绑定 NFC 卡")
            assert "已绑定 NFC 卡" in self.widget.patient_msg.text()
            self.scene("NFC 卡绑定成功，进入挂号并按卡带出患者", self.tab("挂号"))
            reg_tab = self.tab("挂号")
            self.widget.r_card_uid.setText(card_uid)
            self.click(reg_tab, "按卡带出患者")
            assert self.widget.r_patient_id.value() == patient["id"]
            self.click(reg_tab, "刷新医生列表")
            for row in range(self.widget.r_doctor_list.rowCount()):
                if str(self.doc["id"]) == self.widget.r_doctor_list.item(row, 0).text():
                    self.widget.r_doctor_list.selectRow(row)
                    self.widget._pick_doctor(row, 0)
                    break
            self.click(reg_tab, "挂号")
            regs = self.cashier.call("GET", "/registrations/", params={"patient_id": patient["id"]})
            registration = regs[0]
            self.scene("挂号成功，医生接诊并开药（镜头外）")
            enc = self.doctor.call(
                "POST", "/encounters/",
                json={"registration_id": registration["id"], "diagnosis": "收费演示"},
            )
            self.doctor.call(
                "POST", f"/encounters/{enc['id']}/prescriptions",
                json={"drug_id": self.drug["id"], "quantity": 2},
            )
            self.scene("回到收费窗口：扫处方条码带出费用", self.tab("收费"))
            charge_tab = self.tab("收费")
            self.widget.c_scan_code.setText(f"RX{enc['id']:06d}")
            self.click(charge_tab, "扫码带出")
            assert self.widget.c_encounter_id.value() == enc["id"]
            assert "未收费" in self.widget.c_scan_status.text()
            self.click(charge_tab, "查询费用")
            self.click(charge_tab, "收费")
            payments = self.cashier.call("GET", "/payments/", params={"encounter_id": enc["id"]})
            payment = payments[0]
            assert payment["status"] == "paid"
            self.scene(f"收费成功：{payment['amount']:.2f} 元；再扫条码应提示已收费")
            self.widget.c_scan_code.setText(f"RX{enc['id']:06d}")
            self.click(charge_tab, "扫码带出")
            assert "已收费" in self.widget.c_scan_status.text()
            self.click(charge_tab, "收费")
            assert "已收费" in self.widget.charge_msg.text()
            self.scene("重复收费被拦截，进入打印页作废发票", self.tab("打印"))
            print_tab = self.tab("打印")
            self.widget.pr_payment_id.setValue(payment["id"])
            self.widget.void_reason.setText("演示：发票作废")
            self.click(print_tab, "作废发票")
            invoice = self.cashier.call("GET", f"/payments/{payment['id']}")
            assert invoice["invoice_status"] == "void", invoice
            self.scene("发票已作废，回到收费页整单退费", self.tab("收费"))
            charge_tab = self.tab("收费")
            self.widget.refund_payment_id.setValue(payment["id"])
            self.click(charge_tab, "加载收费明细")
            self.click(charge_tab, "全部退")
            refunded = self.cashier.call("GET", f"/payments/{payment['id']}")
            assert refunded["status"] == "refunded", refunded
            self.scene("退费成功，最后看收费员交班/日结", self.tab("交班"))
            shift_tab = self.tab("交班")
            daily = self.cashier.call("GET", "/cashier/daily")
            if not any(row["status"] == "open" for row in daily["shifts"]):
                self.widget.opening_float.setValue(100)
                self.click(shift_tab, "开班")
            self.widget._load_daily()
            self.wait(2.0)
            self.scene("挂号收费独立演示完成：建档/挂号/收费/拦截/发票/退费/交班")
            self.wait(3.0)
            self.timer.stop()
            self.capture()
            self.success = True
        except Exception as exc:  # noqa: BLE001
            print(f"演示失败：{exc}", flush=True)
            self.caption.set_text(f"演示中断：{exc}")
            self.capture()
            self.timer.stop()
            self.error = str(exc)
        finally:
            self.caption.close()
            self.close()
            QApplication.instance().quit()


def encode():
    frames = sorted(FRAME_DIR.glob("frame_*.jpg"))
    if len(frames) < 3:
        print("帧数不足")
        return False
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO.unlink(missing_ok=True)
    result = subprocess.run(
        [
            FFMPEG, "-y", "-framerate", "5",
            "-i", str(FRAME_DIR / "frame_%04d.jpg"),
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
    demo = CashierDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
