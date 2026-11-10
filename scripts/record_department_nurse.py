"""护士站独立全流程慢速演示。

覆盖：分诊登记 → 叫号 → 治疗执行 → 输液同步
      → 未配药直接执行报错 → 配药 → 穿刺 → 巡视 → 完成。
产出：docs/科室独立演示/03_护士站.mp4
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
from his_client.ui.nurse import NurseWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "nurse"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "03_护士站.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class NurseDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("护士站 · nurse")
        self.widget = NurseWidget(ApiClient(BASE, "nurse", "nurse123"))
        self.setCentralWidget(self.widget)
        self.tabs = self.widget.findChild(QTabWidget)
        self.caption = CaptionBar()
        self.screen = QApplication.primaryScreen()
        self.geo = self.screen.availableGeometry()
        self.caption.move(self.geo.x() + 20, self.geo.y() + 34)
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
        self.nurse_api = Api("nurse", "nurse123")
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
        dept = self.admin.call("POST", "/departments/", json={"name": f"护理演示科{self.suffix}"})
        self.doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"护理演示医生{self.suffix}", "department_id": dept["id"]}
        )
        self.drug = self.admin.call(
            "POST", "/drugs/", json={"name": f"护理演示药{self.suffix}", "base_price": 20}
        )
        self.treat_item = self.admin.call(
            "POST", "/charges/items/",
            json={"code": f"NR{self.suffix[-6:]}", "name": f"护理演示治疗{self.suffix}", "category": "treatment", "price": 35},
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"护理演示患者{self.suffix}", "id_number": f"1101011999{self.suffix[-6:]}66"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": self.doc["id"]},
        )
        self.registration = reg
        self.encounter = self.doctor_api.call(
            "POST", "/encounters/",
            json={"registration_id": reg["id"], "diagnosis": "护理演示"},
        )
        self.treatment = self.doctor_api.call(
            "POST", f"/treatments/encounters/{self.encounter['id']}",
            json={"item_id": self.treat_item["id"], "quantity": 1},
        )
        self.doctor_api.call(
            "POST", f"/encounters/{self.encounter['id']}/prescriptions",
            json={
                "drug_id": self.drug["id"], "quantity": 1,
                "dosage": "1g", "frequency": "qd", "route": "静滴", "days": 1,
            },
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
            triage = self.tab("分诊")
            self.scene("护士站演示：先分诊登记", triage)
            self.widget.triage_reg_id.setValue(self.registration["id"])
            self.widget.triage_level.setCurrentIndex(2)
            self.widget.triage_complaint.setText("发热咳嗽 2 天")
            self.widget.triage_temp.setText("38.5")
            self.widget.triage_pulse.setText("102")
            self.widget.triage_resp.setText("22")
            self.widget.triage_sbp.setText("120")
            self.widget.triage_dbp.setText("78")
            self.widget.triage_spo2.setText("96")
            self.widget.triage_pain.setText("3")
            self.click(triage, "登记分诊")
            self.click(triage, "刷新队列")
            for row in range(self.widget.queue_table.rowCount()):
                if self.widget.queue_table.item(row, 1).text() == str(self.registration["id"]):
                    self.widget.queue_table.selectRow(row)
                    break
            self.scene("分诊成功，选中患者叫号")
            self.click(triage, "叫号")
            self.scene("叫号完成，进入治疗执行", self.tab("治疗执行"))
            treat = self.tab("治疗执行")
            self.click(treat, "刷新待执行治疗")
            for row in range(self.widget.treat_table.rowCount()):
                if self.widget.treat_table.item(row, 1).text() == str(self.encounter["id"]):
                    self.widget.treat_table.selectRow(row)
                    break
            self.scene("选中治疗单并执行")
            self.click(treat, "执行选中治疗")
            self.scene("治疗执行完成，进入输液执行", self.tab("输液执行"))
            nursing = self.tab("输液执行")
            self.widget.nurse_encounter_id.setValue(self.encounter["id"])
            self.click(nursing, "同步医嘱")
            self.click(nursing, "刷新执行单")
            target = -1
            for row in range(self.widget.nursing_table.rowCount()):
                if self.widget.nursing_table.item(row, 0).text() == self.patient["name"]:
                    target = row
                    break
            assert target >= 0, "护理执行单没有本次患者"
            self.widget.nursing_table.selectRow(target)
            self.widget._select_nursing(target, 0)
            self.scene("异常路径：未配药直接开始执行")
            self.widget.seat_no.setText("A2")
            self.widget.rate.setText("60")
            self.click(nursing, "开始执行")
            assert "配药" in self.widget.nursing_msg.text(), self.widget.nursing_msg.text()
            self.scene("被拦截；现在配药")
            self.widget.solvent.setText("0.9%氯化钠 250ml")
            self.widget.dose.setText("1g")
            self.widget.batch_no.setText(f"NR-{self.suffix}")
            self.widget.checked_by.setText("nurse")
            self.click(nursing, "配药完成")
            self.scene("配药完成，开始穿刺执行")
            self.click(nursing, "开始执行")
            self.scene("执行中，记录巡视")
            self.widget.nursing_note.setText("滴速正常，无不适")
            self.click(nursing, "巡视记录")
            self.scene("巡视完成，结束输液")
            self.widget.nursing_note.setText("输液完成")
            self.click(nursing, "完成")
            rows = self.nurse_api.call("GET", "/nursing/orders", params={"encounter_id": self.encounter["id"]})
            order = next(row for row in rows if row["encounter_id"] == self.encounter["id"])
            assert order["status"] == "completed", order
            self.scene("护士站演示完成：分诊/叫号/治疗/配药/穿刺/巡视/完成")
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
    demo = NurseDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
