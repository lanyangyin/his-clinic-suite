"""中医/煎药独立全流程慢速演示。

覆盖：医生开饮片处方 → 收费 → 中药房未审核发药拦截 → 审核 → 发药转煎药
      → 煎药未浸泡直接煎煮拦截 → 浸泡 → 煎煮 → 包装 → 发放。
产出：docs/科室独立演示/08_中医煎药.mp4
"""
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QScrollArea, QTabWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.tcm import TcmWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "tcm"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "08_中医煎药.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class TcmDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("中医 / 煎药")
        self.doctor_view = TcmWidget(ApiClient(BASE, "doctor", "doctor123"), role="doctor")
        self.pharmacy_view = TcmWidget(ApiClient(BASE, "pharmacist", "pharm123"), role="pharmacist")
        self.dec_view = TcmWidget(ApiClient(BASE, "decoction", "decoction123"), role="decoction")
        self.views = {
            "doctor": self._wrap(self.doctor_view, "中医诊室 · doctor"),
            "pharmacy": self._wrap(self.pharmacy_view, "中药房 · pharmacist"),
            "decoction": self._wrap(self.dec_view, "煎药室 · decoction"),
        }
        self.current = None
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
        self.suffix = datetime.now().strftime("%H%M%S")

    def _wrap(self, widget, title):
        window = QMainWindow()
        window.setWindowTitle(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        window.setCentralWidget(scroll)
        return window

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def tab(self, widget, text):
        tabs = widget.findChild(QTabWidget)
        for index in range(tabs.count()):
            if text in tabs.tabText(index):
                tabs.setCurrentIndex(index)
                return tabs.widget(index)
        raise RuntimeError(f"找不到页签：{text}")

    def activate(self, key):
        window = self.views[key]
        window.showMaximized()
        window.raise_()
        window.activateWindow()
        self.current = window
        self._active_key = key
        self.caption.show()
        self.caption.raise_()
        self.wait(1.0)

    def scene(self, text, key=None, tab=None):
        print(f"[场景] {text}", flush=True)
        if key is not None:
            self.activate(key)
        if tab is not None:
            self.tab(self._widget(key) if key is not None else self._widget(self._active_key), tab)
        self.caption.set_text(text)
        self.caption.raise_()
        self.wait(2.6)

    def _widget(self, key):
        return {"doctor": self.doctor_view, "pharmacy": self.pharmacy_view, "decoction": self.dec_view}[key]

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
        dept = self.admin.call("POST", "/departments/", json={"name": f"中医演示科{self.suffix}"})
        doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"中医演示医生{self.suffix}", "department_id": dept["id"]}
        )
        self.herb = self.admin.call(
            "POST", "/tcm/herbs",
            json={"code": f"HM{self.suffix[-6:]}", "name": f"黄芪{self.suffix}", "price_per_g": 0.2},
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"中医演示患者{self.suffix}", "id_number": f"1101011993{self.suffix[-6:]}22"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": doc["id"]},
        )
        self.encounter = self.doctor_api.call(
            "POST", "/encounters/",
            json={"registration_id": reg["id"], "diagnosis": "气虚"},
        )

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            for window in self.views.values():
                window.show()
            self.timer.start(250)
            self.caption.show()
            self.wait(1.5)
            self.setup()
            self.scene("中医诊室：开饮片处方", "doctor", "开中药方")
            doc = self.doctor_view
            doc.encounter_id.setValue(self.encounter["id"])
            doc.formula.setText(f"补气方{self.suffix}")
            doc.packs.setValue(3)
            doc.herb_search.setText(self.herb["name"])
            self.click(doc, "查询饮片")
            doc.herb_table.selectRow(0)
            doc.dose.setValue(10)
            self.click(doc, "加入处方")
            self.click(doc, "提交中药处方")
            assert "已开方" in doc.presc_msg.text(), doc.presc_msg.text()
            prescriptions = self.doctor_api.call("GET", "/tcm/prescriptions")
            rx = next(row for row in prescriptions if row["encounter_id"] == self.encounter["id"])
            payment = self.cashier.call(
                "POST", "/payments/", json={"encounter_id": self.encounter["id"], "channel": "cash"}
            )
            self.scene(f"处方已开、收费 {payment['amount']:.2f} 元；中药房先尝试未审核发药", "pharmacy", "中药房")
            ph = self.pharmacy_view
            self.click(ph, "刷新中药处方")
            target = -1
            for row, item in enumerate(ph.rx_rows):
                if item["id"] == rx["id"]:
                    target = row
                    break
            assert target >= 0
            ph.rx_table.selectRow(target)
            ph._select_rx(target, 0)
            self.click(ph, "发药/转煎药")
            assert "未审核" in ph.rx_msg.text(), ph.rx_msg.text()
            self.scene("未审核发药被拦截；审核处方")
            self.click(ph, "审核通过")
            ph.rx_table.selectRow(target)
            ph._select_rx(target, 0)
            self.scene("审核通过，发药并转煎药")
            self.click(ph, "发药/转煎药")
            assert "已发药" in ph.rx_msg.text(), ph.rx_msg.text()
            self.scene("已转煎药；到煎药室先尝试未浸泡直接煎煮", "decoction", "煎药室")
            dec = self.dec_view
            self.click(dec, "刷新煎药单")
            target = -1
            for row, item in enumerate(dec.dec_rows):
                if item["prescription_id"] == rx["id"]:
                    target = row
                    break
            assert target >= 0, "煎药单未生成"
            dec.dec_table.selectRow(target)
            dec._select_dec(target, 0)
            self.click(dec, "开始煎煮")
            assert "浸泡" in dec.dec_msg.text(), dec.dec_msg.text()
            self.scene("未浸泡煎煮被拦截；开始浸泡")
            dec.soak_minutes.setValue(30)
            self.click(dec, "开始浸泡")
            self.scene("浸泡完成，开始煎煮")
            dec.machine.setText("煎药机-1")
            dec.decoct_minutes.setValue(40)
            self.click(dec, "开始煎煮")
            self.scene("煎煮完成，包装")
            dec.bags.setValue(6)
            dec.bag_volume.setValue(200)
            self.click(dec, "包装完成")
            self.scene("包装完成，填写取药人并发放")
            dec.receiver.setText(self.patient["name"])
            self.click(dec, "发放")
            orders = self.api_call_orders()
            order = next(row for row in orders if row["prescription_id"] == rx["id"])
            assert order["status"] in ("issued", "completed"), order
            self.scene("中医/煎药演示完成：开方/审核/发药/浸泡/煎煮/包装/发放", "decoction", "煎药室")
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
            for window in self.views.values():
                window.close()
            QApplication.instance().quit()

    def api_call_orders(self):
        session = ApiClient(BASE, "decoction", "decoction123")
        return session._request("GET", "/tcm/decoction-orders")


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
    demo = TcmDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
