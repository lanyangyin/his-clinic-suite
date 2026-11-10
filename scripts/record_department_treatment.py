"""治疗室独立全流程慢速演示。

覆盖：模板必填拦截 → 新建处置 → 收费 → 知情同意 → 开始（扣套餐耗材）
      → 完成处置 → 自动生成换药随访 → 随访结果记录。
产出：docs/科室独立演示/04_治疗室.mp4
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
from his_client.ui.treatment_room import TreatmentRoomWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "treatment"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "04_治疗室.mp4"
CONSENT = ROOT / "docs" / "dept_preview" / "consent_demo.png"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class TreatmentDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("治疗室 · treatment")
        self.widget = TreatmentRoomWidget(ApiClient(BASE, "treatment", "treatment123"))
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
        self.treatment_api = Api("treatment", "treatment123")
        self.suffix = datetime.now().strftime("%H%M%S")

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def scroll_to(self, widget):
        self.scroll.ensureWidgetVisible(widget, 40, 40)
        self.wait(0.6)

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
        CONSENT.parent.mkdir(parents=True, exist_ok=True)
        pix = QPixmap(360, 120)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        painter.setPen(QPen(QColor("#111827"), 2))
        painter.drawText(30, 65, "Consent Signature")
        painter.end()
        pix.save(str(CONSENT))
        dept = self.admin.call("POST", "/departments/", json={"name": f"治疗演示科{self.suffix}"})
        self.doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"治疗演示医生{self.suffix}", "department_id": dept["id"]}
        )
        charge = self.admin.call(
            "POST", "/charges/items/",
            json={"code": f"TR{self.suffix[-6:]}", "name": f"清创缝合{self.suffix}", "category": "treatment", "price": 80},
        )
        self.material = self.admin.call(
            "POST", "/materials/items/",
            json={"code": f"TM{self.suffix[-6:]}", "name": f"清创包{self.suffix}", "unit": "个", "price": 10, "category": "consumable"},
        )
        self.admin.call(
            "POST", "/materials/stock-in",
            json={"item_id": self.material["id"], "warehouse": "总库", "quantity": 10},
        )
        self.admin.call(
            "PUT", "/treatment-room/templates/debridement",
            json={
                "charge_item_id": charge["id"], "price": 80,
                "materials": [{"material_id": self.material["id"], "quantity": 1, "warehouse": "总库"}],
                "active": True,
            },
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"治疗演示患者{self.suffix}", "id_number": f"1101011990{self.suffix[-6:]}55"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": self.doc["id"]},
        )
        self.encounter = self.doctor_api.call(
            "POST", "/encounters/",
            json={"registration_id": reg["id"], "diagnosis": "右手掌裂伤"},
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
            queue = self.tab("治疗排队")
            self.scene("治疗室演示：先新增治疗室", queue)
            self.widget.room_code.setText(f"TR{self.suffix[-4:]}")
            self.widget.room_name.setText("清创室")
            self.click(queue, "新增治疗室")
            self.scene("新建处置：先不填模板必填项，验证拦截")
            self.widget.patient_id.setValue(self.patient["id"])
            self.widget.encounter_id.setValue(self.encounter["id"])
            self.widget.template.setCurrentIndex(self.widget.template.findData("debridement"))
            self.widget.procedure.setText("清创缝合")
            self.widget.diagnosis.setText("右手掌裂伤")
            self.click(queue, "创建处置")
            assert "请填写必填项" in self.widget.queue_msg.text(), self.widget.queue_msg.text()
            self.scene("必填项被拦截；补填部位/大小后创建")
            self.widget.template_edits["site"].setText("右手掌")
            self.widget.template_edits["size"].setText("3cm")
            self.click(queue, "创建处置")
            cases = self.treatment_api.call("GET", "/treatment-room/cases")
            case = next(row for row in cases if row["patient_id"] == self.patient["id"])
            self.payment = self.cashier.call(
                "POST", "/payments/", json={"encounter_id": self.encounter["id"], "channel": "cash"}
            )
            self.scene(f"处置已创建，收费 {self.payment['amount']:.2f} 元；加载处置")
            self.widget._load_cases()
            target = -1
            for row in range(self.widget.table.rowCount()):
                if self.widget.table.item(row, 0).text() == case["case_no"]:
                    target = row
                    break
            assert target >= 0, "队列没有本次处置"
            self.widget.table.selectRow(target)
            self.widget._select_case(target, 0)
            handle = self.tab("处置记录")
            self.scroll.verticalScrollBar().setValue(0)
            self.scene("知情同意后开始处置，自动扣套餐耗材", handle)
            self.widget.consent.setChecked(True)
            self.widget.consent_signer.setText(self.patient["name"])
            self.widget.consent_relation.setText("本人")
            self.widget.consent_signature_local = str(CONSENT)
            self.widget.consent_signature_path.setText(str(CONSENT))
            self.widget.anesthesia.setText("利多卡因局麻")
            self.widget.findings.setText("右手掌 3cm 裂伤")
            self.click(handle, "开始")
            started = self.treatment_api.call("GET", f"/treatment-room/cases/{case['id']}")
            assert started["kit_applied"] is True
            self.scene("处置中，填写清创缝合记录并完成")
            self.widget.procedure_detail.setText("清创后 3-0 丝线缝合 3 针")
            self.widget.sutures.setText("3-0 丝线 3 针")
            self.widget.dressing.setText("无菌敷料包扎")
            self.scroll_to(self.widget.procedure_detail)
            self.click(handle, "完成")
            done = self.treatment_api.call("GET", f"/treatment-room/cases/{case['id']}")
            assert done["status"] == "completed"
            self.scene("处置完成，查看自动生成的换药随访", self.tab("换药随访"))
            follow = self.tab("换药随访")
            self.widget._load_followups()
            target = -1
            for row in range(self.widget.followup_table.rowCount()):
                if self.widget.followup_table.item(row, 0).text() == self.patient["name"]:
                    target = row
                    break
            assert target >= 0, "没有生成随访"
            self.widget.followup_table.selectRow(target)
            self.scene("填写随访结果与愈合评分")
            self.scroll_to(self.widget.healing_score)
            self.widget.healing_score.setValue(8)
            self.widget.result_note.setText("创面干燥，无渗出")
            self.widget.next_followup.setChecked(False)
            self.click(follow, "标记已随访")
            mark("治疗室-模板-耗材-随访", "完成")
            self.scene("治疗室演示完成：模板/收费/同意/扣耗材/完成/随访")
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


def mark(*_args):
    return None


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
    demo = TreatmentDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
