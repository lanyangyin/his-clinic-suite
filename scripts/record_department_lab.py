"""检验科独立全流程慢速演示。

覆盖：未采样签收拦截 → 采样 → 签收 → 开始检验 → 报告
      → 危急值未通知拦截 → 登记通知 → 审核 → 报告查询。
产出：docs/科室独立演示/07_检验科.mp4
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
from his_client.ui.lab import LabWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "lab"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "07_检验科.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class LabDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("检验科 · lab")
        self.widget = LabWidget(ApiClient(BASE, "lab", "lab123"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.widget)
        self.setCentralWidget(self.scroll)
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
        self.admin = Api("admin", "admin123")
        self.cashier = Api("cashier", "cashier123")
        self.doctor_api = Api("doctor", "doctor123")
        self.lab_api = Api("lab", "lab123")
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

    def select_row(self):
        self.widget._refresh()
        for row in range(self.widget.table.rowCount()):
            if self.widget.table.item(row, 2).text() == self.patient["name"]:
                self.widget.table.selectRow(row)
                self.widget._select_row(row, 0)
                return
        raise RuntimeError("检验列表没有本次患者")

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
        dept = self.admin.call("POST", "/departments/", json={"name": f"检验演示科{self.suffix}"})
        self.doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"检验演示医生{self.suffix}", "department_id": dept["id"]}
        )
        self.item = self.admin.call(
            "POST", "/lab/items/",
            json={"code": f"LB{self.suffix[-6:]}", "name": f"血常规{self.suffix}", "price": 20},
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"检验演示患者{self.suffix}", "id_number": f"1101011992{self.suffix[-6:]}33"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": self.doc["id"]},
        )
        enc = self.doctor_api.call(
            "POST", "/encounters/",
            json={"registration_id": reg["id"], "diagnosis": "检验演示"},
        )
        self.request = self.doctor_api.call(
            "POST", f"/lab/encounters/{enc['id']}/lab-requests",
            json={"item_id": self.item["id"]},
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
            work = self.tab("检验工作台")
            self.scroll.verticalScrollBar().setValue(0)
            self.select_row()
            self.scene("检验科演示：标本未采样，直接签收应被拦截", work)
            self.click(work, "签收")
            assert "未采样" in self.widget.msg.text(), self.widget.msg.text()
            self.scene("被拦截；先采样")
            self.click(work, "采样")
            self.select_row()
            self.scene("采样完成，签收标本")
            self.click(work, "签收")
            self.select_row()
            self.scene("签收完成，开始检验")
            self.click(work, "开始检验")
            self.select_row()
            self.scene("录入结果：白细胞升高，并标记危急值")
            self.widget.result_value.setText("18.5")
            self.widget.result_unit.setText("×10^9/L")
            self.widget.ref_low.setText("4")
            self.widget.ref_high.setText("10")
            self.widget.result_text.setText("WBC 18.5×10^9/L，中性粒细胞 88%")
            self.widget.abnormal.setCurrentIndex(1)
            self.widget.critical.setChecked(True)
            self.widget.critical_note.setText("白细胞显著升高")
            self.click(work, "出具报告")
            self.select_row()
            self.scene("报告已出；危急值未填通知对象，审核应被拦截")
            self.click(work, "审核报告")
            assert "通知对象" in self.widget.msg.text(), self.widget.msg.text()
            self.scene("被拦截；登记危急值通知对象")
            self.widget.notified_to.setText("急诊医生")
            self.click(work, "登记危急值")
            self.select_row()
            self.scene("危急值已登记，审核报告")
            self.click(work, "审核报告")
            self.scene("审核完成，查看报告查询", self.tab("报告查询"))
            query = self.tab("报告查询")
            self.click(query, "刷新已审核报告")
            assert self.widget.reviewed_table.rowCount() >= 1
            self.scene("检验科演示完成：采样/签收/检验/报告/危急值/审核")
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
    demo = LabDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
