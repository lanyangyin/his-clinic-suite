"""药房零售演示：OTC 药 + 口罩/耗材，收款、扣库存、原单退货。

产出：docs/科室独立演示/12_药房零售.mp4
"""
import base64
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTabWidget, QWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402
from scripts.record_ui_windows import CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "retail"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "12_药房零售.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


def headers(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


class RetailDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("药房工作站 · 零售")
        self.view = PharmacyWidget(ApiClient(BASE, "pharmacist", "pharm123"), role="pharmacist")
        self.setCentralWidget(self.view)
        self.caption = CaptionBar()
        self.screen = QApplication.primaryScreen()
        self.geo = self.screen.geometry()
        self.cap_geo = self.screen.availableGeometry()
        self.caption.move(self.cap_geo.x() + 20, self.cap_geo.y() + self.cap_geo.height() - 66)
        self.caption.resize(self.cap_geo.width() - 40, 48)
        self.frames = []
        self.index = 0
        self.point = None
        self.point_until = 0.0
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture)
        self.success = False
        self.error = ""
        self.suffix = datetime.now().strftime("%H%M%S")

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def scene(self, text):
        print(f"[场景] {text}", flush=True)
        self.caption.set_text(text)
        self.caption.show()
        self.caption.raise_()
        self.wait(2.4)

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
        admin = headers("admin", "admin123")
        pharmacist = headers("pharmacist", "pharm123")
        drug = requests.post(
            f"{BASE}/drugs/",
            headers=admin,
            json={
                "name": f"零售创可贴{self.suffix}",
                "spec": "100片",
                "unit": "盒",
                "base_price": 8,
                "is_otc": True,
            },
            timeout=30,
        ).json()
        requests.post(
            f"{BASE}/pharmacy/stock-in",
            headers=pharmacist,
            json={
                "drug_id": drug["id"],
                "batch_no": f"OTCB{self.suffix}",
                "expiry": (date.today() + timedelta(days=365)).isoformat(),
                "quantity": 10,
            },
            timeout=30,
        )
        material = requests.post(
            f"{BASE}/materials/items/",
            headers=admin,
            json={
                "code": f"MASK{self.suffix}",
                "name": f"医用口罩{self.suffix}",
                "unit": "个",
                "price": 1,
                "category": "consumable",
            },
            timeout=30,
        ).json()
        requests.post(
            f"{BASE}/materials/stock-in",
            headers=admin,
            json={"item_id": material["id"], "warehouse": "药房", "quantity": 50},
            timeout=30,
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
            self.view._load_retail_catalog()
            tabs = self.view.findChild(QTabWidget)
            for index in range(tabs.count()):
                if tabs.tabText(index) == "零售":
                    tabs.setCurrentIndex(index)
                    break
            self.wait(1.0)
            self.scene("药房零售：选非处方药（创可贴）")
            self.view.retail_type.setCurrentIndex(0)
            self.view.retail_qty.setValue(2)
            self.click(self.view, "加入零售单")
            self.scene("再选口罩等耗材，不建就诊")
            self.view.retail_type.setCurrentIndex(1)
            self.view.retail_qty.setValue(5)
            self.click(self.view, "加入零售单")
            self.scene(f"零售合计 {self.view.retail_total.text()}，收款")
            self.click(self.view, "收款并打印小票")
            assert "零售成功" in self.view.retail_msg.text(), self.view.retail_msg.text()
            self.scene(self.view.retail_msg.text())
            sale_id = self.view.retail_last_sale_id
            assert sale_id
            self.view.retail_refund_id.setValue(sale_id)
            self.scene("原单退货，库存回补")
            self.click(self.view, "原单退货（库存回补）")
            assert "已退货" in self.view.retail_msg.text(), self.view.retail_msg.text()
            self.scene(self.view.retail_msg.text())
            self.wait(2.0)
            self.timer.stop()
            self.capture()
            self.success = True
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
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
    demo = RetailDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
