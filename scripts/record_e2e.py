"""录制全流程测试过程：运行 E2E + 实时展示客户端界面，输出 MP4。

运行：
    .venv\\Scripts\\python.exe scripts\\record_e2e.py
产出：
    docs/全流程测试录像.mp4
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.doctor import DoctorWidget  # noqa: E402
from his_client.ui.nurse import NurseWidget  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "e2e_frames"
LOG_PATH = ROOT / "docs" / "e2e_run.log"
VIDEO_PATH = ROOT / "docs" / "全流程测试录像.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class RecorderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HIS 全流程测试录像 · 7 账号 · 客户端界面实时同步")
        self.resize(1440, 920)
        self.frame_index = 0
        self.log_offset = 0
        self.started_at = time.time()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        title = QLabel("HIS 全流程测试（真实 API + 多角色客户端界面同步）")
        title.setStyleSheet("font-size:18px;font-weight:bold;padding:6px;color:#1f2937")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.doctor = DoctorWidget(ApiClient(BASE, "doctor", "doctor123"))
        self.pharmacy = PharmacyWidget(
            ApiClient(BASE, "pharmacist", "pharm123"), role="pharmacist"
        )
        self.warehouse = PharmacyWidget(
            ApiClient(BASE, "warehouse", "warehouse123"), role="warehouse"
        )
        self.nurse = NurseWidget(ApiClient(BASE, "nurse", "nurse123"))
        self.tabs.addTab(self.doctor, "医生工作站（接诊）")
        self.tabs.addTab(self.pharmacy, "药房工作站（领用/库存）")
        self.tabs.addTab(self.warehouse, "库房工作站（出库/总库）")
        self.tabs.addTab(self.nurse, "护士工作站（队列）")
        self._select_inner_tab(self.doctor, "接诊")
        self._select_inner_tab(self.pharmacy, "领用出库")
        self._select_inner_tab(self.warehouse, "出库处理")
        self._select_inner_tab(self.nurse, "分诊叫号")
        layout.addWidget(self.tabs, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family:Consolas,monospace;font-size:12px")
        self.log.setMinimumHeight(170)
        layout.addWidget(self.log, 0)

        self.status = QLabel("准备启动全流程测试…")
        self.status.setStyleSheet("padding:4px;color:#374151")
        layout.addWidget(self.status)
        self.setCentralWidget(central)

        self.process: subprocess.Popen | None = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.finish_timer = QTimer(self)
        self.finish_timer.setSingleShot(True)
        self.finish_timer.timeout.connect(self.encode_and_quit)

    def start(self) -> None:
        FRAME_DIR.mkdir(parents=True, exist_ok=True)
        for old in FRAME_DIR.glob("*.png"):
            old.unlink()
        LOG_PATH.write_text("", encoding="utf-8")
        self.capture()
        self.timer.start(500)
        self.log.append("启动全流程测试脚本…")
        env = os.environ.copy()
        env["E2E_STEP_DELAY"] = "0.12"
        env["E2E_VERBOSE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        log_file = open(LOG_PATH, "w", encoding="utf-8")
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "e2e_full_flow.py")],
            cwd=str(ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        self.log_file = log_file

    @staticmethod
    def _select_inner_tab(widget: QWidget, text: str) -> None:
        tabs = widget.findChild(QTabWidget)
        if not tabs:
            return
        for index in range(tabs.count()):
            if text in tabs.tabText(index):
                tabs.setCurrentIndex(index)
                return

    def tick(self) -> None:
        elapsed = int(time.time() - self.started_at)
        self.status.setText(f"测试运行中… 已执行 {elapsed} 秒")
        try:
            self.doctor._load_pending_registrations()
        except Exception:
            pass
        try:
            self.pharmacy._load_outbounds()
            self.pharmacy._load_stocks()
        except Exception:
            pass
        try:
            self.warehouse._load_handle_orders()
            self.warehouse._load_warehouse_stocks()
        except Exception:
            pass
        try:
            self.nurse._load_queue()
        except Exception:
            pass
        self.read_log()
        self.capture()
        if self.process and self.process.poll() is not None:
            self.timer.stop()
            code = self.process.returncode
            self.status.setText(
                f"测试{'通过' if code == 0 else f'失败（退出码 {code}）'} · "
                f"耗时 {int(time.time() - self.started_at)} 秒 · 正在生成录像…"
            )
            self.log.append(self.status.text())
            self.capture()
            self.finish_timer.start(2500)

    def read_log(self) -> None:
        try:
            text = LOG_PATH.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return
        if len(text) > self.log_offset:
            chunk = text[self.log_offset:]
            self.log_offset = len(text)
            self.log.append(chunk.rstrip())
            self.log.verticalScrollBar().setValue(
                self.log.verticalScrollBar().maximum()
            )

    def capture(self) -> None:
        self.frame_index += 1
        path = FRAME_DIR / f"frame_{self.frame_index:04d}.png"
        self.grab().save(str(path))

    def encode_and_quit(self) -> None:
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
            "1",
            "-i",
            str(FRAME_DIR / "frame_%04d.png"),
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x111827",
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
    print(f"录像已生成：{VIDEO_PATH}（{len(frames)} 帧，{VIDEO_PATH.stat().st_size/1024/1024:.1f} MB）")
    return True


def main() -> int:
    app = QApplication(sys.argv)
    window = RecorderWindow()
    window.show()
    app.processEvents()
    window.start()
    app.exec()
    return 0 if encode_video() else 1


if __name__ == "__main__":
    raise SystemExit(main())
