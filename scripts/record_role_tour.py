"""人事/手术室独立登录巡检：真实登录后逐个点击页签。"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTabWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.ui.main_window import MainWindow  # noqa: E402
from scripts.record_ui_windows import CaptionBar, LoginMixin  # noqa: E402

BASE = "http://127.0.0.1:8001"
ROLES = {
    "hr": ("hr_gui", "hr123", "15_人事工作站.mp4", "人事工作站"),
    "surgery": ("surgery", "surgery123", "16_手术室.mp4", "手术室工作站"),
}
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class RoleTour(LoginMixin):
    def __init__(self, key):
        self.key = key
        self.user, self.password, self.video_name, self.title = ROLES[key]
        self.frame_dir = ROOT / "docs" / "dept_frames" / self.key
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
        self.window = None
        self.success = False
        self.error = ""

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def scene(self, text):
        print(f"[场景] {text}", flush=True)
        self.caption.set_text(text)
        self.caption.show()
        self.caption.raise_()
        self.wait(1.5)

    def capture(self):
        pixmap = self.screen.grabWindow(0)
        image = pixmap.toImage().scaled(1600, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.index += 1
        image.save(str(self.frame_dir / f"frame_{self.index:04d}.jpg"), "JPEG", 86)

    def click_tab(self, tabs: QTabWidget, index: int):
        bar = tabs.tabBar()
        rect = bar.tabRect(index)
        self.point = bar.mapToGlobal(rect.center())
        self.point_until = time.time() + 1.0
        QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier, rect.center())

    def run(self):
        try:
            self.frame_dir.mkdir(parents=True, exist_ok=True)
            for old in self.frame_dir.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.caption.show()
            api, user = self.perform_login(self.user, self.password)
            self.window = MainWindow(api, user)
            self.window.showFullScreen()
            self.window.raise_()
            self.window.activateWindow()
            self.caption.show()
            self.caption.raise_()
            self.wait(1.2)
            self.scene(f"{self.title}：登录成功")
            top = self.window.tabs
            for index in range(top.count()):
                self.click_tab(top, index)
                self.scene(f"{self.title}：{top.tabText(index)}")
                page = top.widget(index)
                inner = page.findChild(QTabWidget) if page else None
                if inner:
                    for sub in range(inner.count()):
                        self.click_tab(inner, sub)
                        self.scene(f"{top.tabText(index)}：{inner.tabText(sub)}")
            self.scene(f"{self.title}巡检完成")
            self.wait(1.5)
            self.timer.stop()
            self.capture()
            self.success = True
        except Exception as exc:  # noqa: BLE001
            print(f"巡检失败：{exc}", flush=True)
            self.caption.set_text(f"巡检中断：{exc}")
            self.capture()
            self.timer.stop()
            self.error = str(exc)
        finally:
            self.caption.close()
            if self.window:
                self.window.close()
            QApplication.instance().quit()


def encode(frame_dir, video_name):
    frames = sorted(frame_dir.glob("frame_*.jpg"))
    if len(frames) < 3:
        return False
    video = ROOT / "docs" / "科室独立演示" / video_name
    result = subprocess.run(
        [FFMPEG, "-y", "-framerate", "5", "-i", str(frame_dir / "frame_%04d.jpg"),
         "-vf", "scale=1600:900:force_original_aspect_ratio=decrease,"
                "pad=1600:900:(ow-iw)/2:(oh-ih)/2:color=0x0f172a",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(video)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"录像：{video}（{len(frames)} 帧）")
    return result.returncode == 0 and video.is_file()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=ROLES)
    args = parser.parse_args()
    app = QApplication(sys.argv)
    demo = RoleTour(args.role)
    QTimer.singleShot(500, demo.run)
    app.exec()
    ok = encode(demo.frame_dir, demo.video_name)
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
