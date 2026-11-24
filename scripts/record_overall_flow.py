"""整体测试：管理员真实登录后，逐个点击 24 个工作站页签。"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.main_window import MainWindow  # noqa: E402
from scripts.record_ui_windows import CaptionBar, LoginMixin  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "overall"
VIDEO = ROOT / "docs" / "科室独立演示" / "21_整体测试.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class OverallDemo(LoginMixin):
    def __init__(self):
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
        self.window = None

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def scene(self, text):
        print(f"[场景] {text}", flush=True)
        self.caption.set_text(text)
        self.caption.show()
        self.caption.raise_()
        self.wait(1.3)
        self.capture()

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

    def click_tab(self, index: int):
        bar = self.window.tabs.tabBar()
        rect = bar.tabRect(index)
        self.point = bar.mapToGlobal(rect.center())
        self.point_until = time.time() + 1.0
        QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier, rect.center())

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.caption.show()
            api, user = self.perform_login("admin", "admin123")
            self.window = MainWindow(api, user)
            self.window.showFullScreen()
            self.window.raise_()
            self.window.activateWindow()
            self.caption.show()
            self.caption.raise_()
            self.wait(1.5)
            total = self.window.tabs.count()
            self.scene(f"整体测试：管理员登录成功，工作站页签 {total} 个")
            for index in range(total):
                self.click_tab(index)
                title = self.window.tabs.tabText(index)
                self.scene(f"整体巡检：{index + 1}/{total} {title}")
            self.scene(f"整体测试完成：{total}/{total} 个工作站页签可打开")
            self.wait(2.5)
            self.timer.stop()
            self.capture()
            self.success = True
        except Exception as exc:  # noqa: BLE001
            print(f"整体演示失败：{exc}", flush=True)
            self.caption.set_text(f"整体演示中断：{exc}")
            self.capture()
            self.timer.stop()
            self.error = str(exc)
        finally:
            self.caption.close()
            if self.window:
                self.window.close()
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
    demo = OverallDemo()
    QTimer.singleShot(500, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
