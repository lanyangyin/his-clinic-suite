"""影像科独立全流程慢速演示：登录 → 待检查 → 结构化报告 → 已报告 → 审核。"""
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.radiology import RadiologyWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar, LoginMixin  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "radiology"
VIDEO = ROOT / "docs" / "科室独立演示" / "13_影像科.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class RadiologyDemo(LoginMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("影像科 · radiology")
        self.widget = RadiologyWidget(ApiClient(BASE, "radiology", "rad123"))
        self.setCentralWidget(self.widget)
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
        self.radiology_api = Api("radiology", "rad123")
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
        image.save(str(FRAME_DIR / f"frame_{self.index:04d}.jpg"), "JPEG", 86)
        self.frames.append(FRAME_DIR / f"frame_{self.index:04d}.jpg")

    def setup(self):
        dept = self.admin.call("POST", "/departments/", json={"name": f"影像演示科{self.suffix}"})
        doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"影像演示医生{self.suffix}", "department_id": dept["id"]}
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"影像演示患者{self.suffix}", "id_number": f"1101011992{self.suffix[-6:]}55"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": doc["id"]},
        )
        enc = self.doctor_api.call(
            "POST", "/encounters/", json={"registration_id": reg["id"], "diagnosis": "咳嗽"}
        )
        item = self.admin.call(
            "POST", "/pacs/items/",
            json={"code": f"RAD{self.suffix[-6:]}", "name": "胸部 CT", "body_part": "胸部", "price": 180},
        )
        self.request = self.doctor_api.call(
            "POST", f"/pacs/encounters/{enc['id']}/imaging-requests", json={"item_id": item["id"]}
        )

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.caption.show()
            self.perform_login("radiology", "rad123")
            self.showMaximized()
            self.caption.show()
            self.wait(1.2)
            self.setup()
            self.widget._load()
            self.scene("影像科：待检查列表")
            target = -1
            for row in range(self.widget.table.rowCount()):
                if self.patient["name"] in self.widget.table.item(row, 1).text():
                    target = row
                    break
            assert target >= 0, "待检查列表没有本次患者"
            self.widget.table.selectRow(target)
            self.widget._select(target, 0)
            self.scene("选中检查，录入影像所见与诊断意见")
            self.widget.report.setPlainText("双肺纹理增粗，未见明显实变影。")
            self.widget.impression.setPlainText("支气管炎可能，建议结合临床。")
            self.widget.image_url.setText("http://pacs.local/study/demo.dcm")
            self.widget.study_uid.setText("1.2.840.113619.2.55.3.604688.1")
            self.widget.series_uid.setText("1.2.840.113619.2.55.3.604688.1.1")
            self.widget.modality.setText("CT")
            self.click(self.widget, "提交报告")
            reported = self.radiology_api.call("GET", f"/pacs/requests/{self.request['id']}")
            assert reported["status"] == "reported", reported
            self.scene("报告已提交，切换已报告列表进行审核")
            self.widget.status_filter.setCurrentIndex(self.widget.status_filter.findData("reported"))
            self.widget._load()
            target = -1
            for row in range(self.widget.table.rowCount()):
                if self.patient["name"] in self.widget.table.item(row, 1).text():
                    target = row
                    break
            assert target >= 0, "已报告列表没有本次患者"
            self.widget.table.selectRow(target)
            self.widget._select(target, 0)
            self.widget.review_note.setText("报告规范，审核通过")
            self.click(self.widget, "审核通过")
            reviewed = self.radiology_api.call("GET", f"/pacs/requests/{self.request['id']}")
            assert reviewed["status"] == "reviewed", reviewed
            self.scene("影像科演示完成：结构化报告/StudyUID/审核")
            self.wait(2.5)
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
    VIDEO.parent.mkdir(parents=True, exist_ok=True)
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
    demo = RadiologyDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
