"""药房独立全流程慢速演示。

覆盖：待发药队列 → 叫号 → 错误取药码拦截 → 正确核对
      → 取药人/签字 → 发药 → 重复发药拦截 → 退药。
产出：docs/科室独立演示/05_药房.mp4
"""
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QScrollArea, QTabWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "pharmacy"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "05_药房.mp4"
SIGNATURE = ROOT / "docs" / "dept_preview" / "signature_demo.png"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class PharmacyDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("药房 · pharmacist")
        self.widget = PharmacyWidget(ApiClient(BASE, "pharmacist", "pharm123"), role="pharmacist")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.widget)
        self.setCentralWidget(self.scroll)
        self.tabs = self.widget.findChild(QTabWidget)
        self.caption = CaptionBar()
        self.screen = QApplication.primaryScreen()
        self.geo = self.screen.availableGeometry()
        self.caption.move(self.geo.x() + 20, self.geo.y() + self.geo.height() - 66)
        self.caption.resize(self.geo.width() - 40, 48)
        self.frames = []
        self.index = 0
        self.point = None
        self.point_until = 0.0
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture)
        self.success = False
        self.error = ""
        self.admin = Api("admin", "admin123")
        self.cashier = Api("cashier", "cashier123")
        self.doctor_api = Api("doctor", "doctor123")
        self.pharmacist_api = Api("pharmacist", "pharm123")
        self.suffix = datetime.now().strftime("%H%M%S")

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def tab(self, text):
        for index in range(self.tabs.count()):
            if text in self.tabs.tabText(index):
                self.tabs.setCurrentIndex(index)
                return self.tabs.widget(index)
        raise RuntimeError(f"找不到页签：{text}")

    def scene(self, text, tab=None):
        print(f"[场景] {text}", flush=True)
        if tab is not None:
            self.tabs.setCurrentWidget(tab)
        self.caption.set_text(text)
        self.caption.show()
        self.caption.raise_()
        self.wait(2.6)

    def click(self, container, text):
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
        path = FRAME_DIR / f"frame_{self.index:04d}.jpg"
        image.save(str(path), "JPEG", 86)
        self.frames.append(path)

    def setup(self):
        SIGNATURE.parent.mkdir(parents=True, exist_ok=True)
        pix = QPixmap(360, 120)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        painter.setPen(QPen(QColor("#111827"), 2))
        painter.drawText(30, 65, "Demo Signature")
        painter.end()
        pix.save(str(SIGNATURE))
        dept = self.admin.call("POST", "/departments/", json={"name": f"药房演示科{self.suffix}"})
        self.doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"药房演示医生{self.suffix}", "department_id": dept["id"]}
        )
        self.drug = self.admin.call(
            "POST", "/drugs/", json={"name": f"药房演示药{self.suffix}", "base_price": 12}
        )
        self.pharmacist_api.call(
            "POST", "/pharmacy/stock-in",
            json={
                "drug_id": self.drug["id"], "batch_no": f"PH-{self.suffix}",
                "expiry": "2027-12-31", "quantity": 10,
            },
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"药房演示患者{self.suffix}", "id_number": f"1101011991{self.suffix[-6:]}44"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": self.doc["id"]},
        )
        self.encounter = self.doctor_api.call(
            "POST", "/encounters/",
            json={"registration_id": reg["id"], "diagnosis": "药房演示"},
        )
        self.doctor_api.call(
            "POST", f"/encounters/{self.encounter['id']}/prescriptions",
            json={"drug_id": self.drug["id"], "quantity": 2},
        )
        self.payment = self.cashier.call(
            "POST", "/payments/", json={"encounter_id": self.encounter["id"], "channel": "cash"}
        )

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.showMaximized()
            self.caption.show()
            self.wait(1.5)
            self.setup()
            disp = self.tab("发药")
            self.scroll.verticalScrollBar().setValue(0)
            self.widget._load_worklist()
            target = -1
            for row, item in enumerate(self.widget.worklist):
                if item["encounter_id"] == self.encounter["id"]:
                    target = row
                    break
            assert target >= 0, "待发药队列没有本次患者"
            self.widget.disp_scan.setText(f"RX{self.encounter['id']:06d}")
            self.click(disp, "扫码定位")
            assert self.widget.disp_encounter_id.value() == self.encounter["id"]
            assert "扫码定位" in self.widget.disp_msg.text()
            self.scene("药房演示：扫码定位本次患者", disp)
            self.scene("先叫号，窗口 2 号")
            self.widget.disp_window.setText("2号窗")
            self.click(disp, "叫号")
            calls = self.pharmacist_api.call("GET", "/pharmacy/worklist")
            row = next(x for x in calls if x["encounter_id"] == self.encounter["id"])
            assert row["call_status"] == "called"
            code = row["pickup_code"]
            self.scene(f"叫号完成，取药码 {code}；先故意输错取药码")
            self.widget.pickup_code.setText("P000000")
            self.click(disp, "核对取药码")
            assert "不存在" in self.widget.disp_msg.text(), self.widget.disp_msg.text()
            self.scene("错误码被拦截；重新选中患者并核对正确取药码")
            self.widget.worklist_table.selectRow(target)
            self.widget._select_worklist(target, 0)
            self.click(disp, "核对取药码")
            assert "通过" in self.widget.disp_msg.text(), self.widget.disp_msg.text()
            self.scene("核对通过，填写取药人并选择签名")
            self.widget.receiver_name.setText(self.patient["name"])
            self.widget.receiver_relation.setText("本人")
            self.widget.signature_path.setText(str(SIGNATURE))
            self.scroll.ensureWidgetVisible(self.widget.receiver_name)
            self.scene("执行核对发药")
            self.click(disp, "核对发药")
            records = self.pharmacist_api.call("GET", "/pharmacy/worklist")
            assert all(x["encounter_id"] != self.encounter["id"] for x in records)
            self.scene("发药成功；再次发药应被拦截")
            self.click(disp, "核对发药")
            assert "已发药" in self.widget.disp_msg.text(), self.widget.disp_msg.text()
            self.scene("重复发药被拦截；执行退药回补库存")
            self.click(disp, "退药（库存回补）")
            assert "退药成功" in self.widget.return_msg.text(), self.widget.return_msg.text()
            stock = self.pharmacist_api.call("GET", f"/pharmacy/stocks?drug_id={self.drug['id']}")
            assert sum(x["quantity"] for x in stock) == 10
            self.scene("药房演示完成：队列/叫号/错误码/核对/签字/发药/拦截/退药")
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
        return False
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
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
    demo = PharmacyDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())

