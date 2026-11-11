"""收费后台独立慢速演示（真实 PySide）。

覆盖：收费员开班 → 日结 → 交班。
产出：docs/科室独立演示/10b_收费后台.mp4
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
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTabWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.cashier import CashierWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "cashier_backoffice"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "10b_收费后台.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class CashierBackoffice(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("收费后台 · cashier")
        self.widget = CashierWidget(ApiClient(BASE, "cashier", "cashier123"))
        self.setCentralWidget(self.widget)
        self.tabs = self.widget.findChild(QTabWidget)
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
        self.cashier = Api("cashier", "cashier123")
        self.suffix = datetime.now().strftime("%H%M%S")

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def scene(self, text):
        print(f"[场景] {text}", flush=True)
        self.caption.set_text(text)
        self.caption.show()
        self.caption.raise_()
        self.wait(2.8)

    def click(self, text):
        for button in self.widget.findChildren(QPushButton):
            if button.text().strip() == text and button.isVisible():
                self.point = button.mapToGlobal(button.rect().center())
                self.point_until = time.time() + 1.2
                QTest.mouseClick(button, Qt.LeftButton)
                self.wait(1.9)
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

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.showMaximized()
            self.caption.show()
            self.wait(1.5)
            tab = None
            for index in range(self.tabs.count()):
                if "交班" in self.tabs.tabText(index):
                    self.tabs.setCurrentIndex(index)
                    tab = self.tabs.widget(index)
                    break
            assert tab is not None
            self.widget._load_daily()
            if self.widget.open_shift_id is None:
                self.scene("收费后台演示：当前无未交班记录，先开班")
                self.widget.opening_float.setValue(100)
                self.widget.shift_note.setText("后台演示开班")
                self.click("开班")
            else:
                self.scene("收费后台演示：沿用当前未交班记录")
            self.widget._load_daily()
            self.scene("查看收费日结：交班单、备用金、应有现金")
            self.widget.counted_cash.setValue(float(self.widget.opening_float.value()))
            self.widget.shift_note.setText("后台演示交班")
            self.scene("填写实收现金并交班")
            shift_id = self.widget.open_shift_id
            self.click("交班")
            shifts = self.cashier.call("GET", "/cashier/shifts")
            closed = next((row for row in shifts if row["id"] == shift_id), None)
            if closed is not None:
                assert closed["status"] == "closed", closed
            self.widget._load_daily()
            self.scene("交班完成，日结列表已刷新")
            self.wait(3.0)
            self.timer.stop()
            self.capture()
            self.success = True
        except Exception as exc:  # noqa: BLE001
            print(f"演示失败：{exc}", flush=True)
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
    demo = CashierBackoffice()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
