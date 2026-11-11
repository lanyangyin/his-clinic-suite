"""医生站独立全流程慢速演示。

覆盖：工作台队列 → 未填诊断报错 → 接诊 → 病历保存/签名
      → 开方 → 开检验 → 开治疗 → 历史诊疗。
产出：docs/科室独立演示/02_医生站.mp4
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
from his_client.ui.doctor import DoctorWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "doctor"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "02_医生站.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class DoctorDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("医生站 · doctor")
        self.widget = DoctorWidget(ApiClient(BASE, "doctor", "doctor123"))
        self.setCentralWidget(self.widget)
        self.tabs = self.widget.tabs
        self.caption = CaptionBar()
        self.screen = QApplication.primaryScreen()
        self.geo = self.screen.geometry()
        self.cap_geo = self.screen.availableGeometry()
        self.caption.move(self.cap_geo.x() + 20, self.cap_geo.y() + 34)
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

    def select_combo(self, combo, contains):
        for index in range(combo.count()):
            if contains in combo.itemText(index):
                combo.setCurrentIndex(index)
                return
        raise RuntimeError(f"下拉框找不到：{contains}")

    def capture(self):
        pixmap = self.screen.grabWindow(0)
        if self.point and time.time() < self.point_until:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            scale_x = pixmap.width() / max(1, self.geo.width())
            scale_y = pixmap.height() / max(1, self.geo.height())
            point = QPoint(
                int((self.point.x() - self.geo.x()) * scale_x),
                int((self.point.y() - self.geo.y()) * scale_y),
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
        self.dept = self.admin.call("POST", "/departments/", json={"name": f"医生演示科{self.suffix}"})
        self.doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"医生演示医生{self.suffix}", "department_id": self.dept["id"]}
        )
        self.drug = self.admin.call(
            "POST", "/drugs/", json={"name": f"医生演示药{self.suffix}", "base_price": 16}
        )
        self.lab = self.admin.call(
            "POST", "/lab/items/", json={"code": f"LD{self.suffix[-6:]}", "name": f"医生演示检验{self.suffix}", "price": 25}
        )
        self.treat = self.admin.call(
            "POST", "/charges/items/",
            json={"code": f"TD{self.suffix[-6:]}", "name": f"医生演示治疗{self.suffix}", "category": "treatment", "price": 30},
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"医生演示患者{self.suffix}", "id_number": f"1101011998{self.suffix[-6:]}77"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": self.doc["id"]},
        )
        self.registration = reg

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
            work = self.tab("门诊工作台")
            self.widget._load_workbench()
            self.scene("医生站演示：未选患者直接点开始接诊", work)
            self.click(work, "开始接诊")
            assert "请先选择患者" in self.widget.wb_summary.text(), self.widget.wb_summary.text()
            self.scene("异常路径被拦截；现在选中本次患者")
            target = -1
            for row in range(self.widget.wb_table.rowCount()):
                if self.patient["name"] in self.widget.wb_table.item(row, 1).text():
                    target = row
                    break
            assert target >= 0, "工作台队列没有本次患者"
            self.widget.wb_table.selectRow(target)
            self.widget._select_workbench(target, 0)
            self.scene("填写诊断并开始接诊")
            code_index = self.widget.wb_diagnosis_code.findData("J06.9")
            if code_index >= 0:
                self.widget.wb_diagnosis_code.setCurrentIndex(code_index)
            self.widget.wb_diagnosis.setText("急性上呼吸道感染")
            self.click(work, "开始接诊")
            encounters = self.doctor_api.call(
                "GET", "/encounters/", params={"patient_id": self.patient["id"]}
            )
            self.encounter = encounters[0]
            assert self.encounter["id"]

            lab_request = self.doctor_api.call(
                "POST", f"/lab/encounters/{self.encounter['id']}/lab-requests",
                json={"item_id": self.lab["id"]},
            )
            for action in ("collect", "receive", "start"):
                self.lab_api.call("POST", f"/lab/requests/{lab_request['id']}/{action}")
            self.lab_api.call(
                "POST", f"/lab/requests/{lab_request['id']}/report",
                json={
                    "result": "WBC 25.0×10^9/L",
                    "result_value": 25.0,
                    "result_unit": "×10^9/L",
                    "critical_flag": True,
                    "critical_note": "白细胞显著升高",
                    "critical_notified_to": "急诊医生",
                },
            )
            self.widget._load_workbench()
            for row in range(self.widget.wb_table.rowCount()):
                if self.patient["name"] in self.widget.wb_table.item(row, 1).text():
                    self.widget.wb_table.selectRow(row)
                    self.widget._select_workbench(row, 0)
                    break
            self.widget._load_critical_alerts()
            self.scene("检验科报告危急值，医生工作台红色提醒")
            self.widget.critical_table.selectRow(0)
            self.widget._select_critical(0, 0)
            self.widget.critical_note.setText("已电话回读并确认")
            self.click(work, "确认危急值")
            ack = self.doctor_api.call("GET", f"/lab/requests/{lab_request['id']}")
            assert ack.get("critical_ack_by"), ack
            self.scene("危急值已确认，继续病历书写与签名", self.tab("病历"))
            record_tab = self.tab("病历")
            self.widget.mr_encounter_id.setValue(self.encounter["id"])
            self.click(record_tab, "载入病历")
            self.widget.record_edits["chief_complaint"].setPlainText("发热咳嗽 2 天")
            self.widget.record_edits["present_illness"].setPlainText("受凉后发热，最高 38.3℃")
            self.widget.record_edits["physical_exam"].setPlainText("咽充血，双肺呼吸音清")
            self.widget.record_edits["treatment_advice"].setPlainText("抗感染，多饮水")
            self.click(record_tab, "保存 / 更新")
            self.click(record_tab, "签名锁定")
            record = self.doctor_api.call("GET", f"/encounters/{self.encounter['id']}/medical-record")
            assert record.get("signed_by"), record
            self.scene("病历已签名，进入开方", self.tab("开方"))
            rx_tab = self.tab("开方")
            self.widget.rx_encounter_id.setValue(self.encounter["id"])
            self.click(rx_tab, "刷新药品目录")
            for row in range(self.widget.drug_table.rowCount()):
                if self.widget.drug_table.item(row, 1).text() == self.drug["name"]:
                    self.widget.drug_table.selectRow(row)
                    self.widget.rx_drug_id.setText(self.widget.drug_table.item(row, 0).text())
                    break
            self.widget.rx_quantity.setValue(2)
            self.widget.rx_dosage.setText("1 片")
            self.widget.rx_frequency.setText("tid")
            self.widget.rx_route.setText("口服")
            self.click(rx_tab, "开方")
            self.scene("处方已开，开检验单", self.tab("检验"))
            exam_tab = self.tab("检验")
            self.widget.exam_encounter_id.setValue(self.encounter["id"])
            self.click(exam_tab, "刷新检验项目")
            self.select_combo(self.widget.lab_combo, self.lab["name"])
            self.click(exam_tab, "开检验单")
            self.scene("检验已开，开治疗单", self.tab("治疗"))
            treat_tab = self.tab("治疗")
            self.widget.treat_encounter_id.setValue(self.encounter["id"])
            self.click(treat_tab, "刷新治疗项目")
            self.select_combo(self.widget.treat_combo, self.treat["name"])
            self.widget.treat_quantity.setValue(1)
            self.click(treat_tab, "开治疗单")
            self.scene("处方/检验/治疗已开，最后查看历史诊疗", self.tab("历史诊疗"))
            history_tab = self.tab("历史诊疗")
            self.widget.history_name.setText(self.patient["name"])
            self.click(history_tab, "查询患者")
            for row in range(self.widget.history_patient_table.rowCount()):
                if self.widget.history_patient_table.item(row, 1).text() == self.patient["name"]:
                    self.widget.history_patient_table.selectRow(row)
                    self.widget._select_history_patient(row, 0)
                    break
            assert self.widget.history_enc_table.rowCount() >= 1
            self.scene("历史诊疗可见，医生站演示完成")
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
    demo = DoctorDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
