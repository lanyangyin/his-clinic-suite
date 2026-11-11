"""病案室独立全流程慢速演示。

覆盖：建档 → 未填库位归档拦截 → 归档上架 → 借阅 → 归还
      → 复印登记 → 封存 → 启封。
产出：docs/科室独立演示/09_病案室.mp4
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
from his_client.ui.archive import ArchiveWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "archive"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "09_病案室.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class ArchiveDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("病案档案工作站 · archive")
        self.widget = ArchiveWidget(ApiClient(BASE, "archive", "archive123"))
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
        self.archive_api = Api("archive", "archive123")
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
        dept = self.admin.call("POST", "/departments/", json={"name": f"病案演示科{self.suffix}"})
        doc = self.admin.call(
            "POST", "/doctors/", json={"name": f"病案演示医生{self.suffix}", "department_id": dept["id"]}
        )
        self.patient = self.cashier.call(
            "POST", "/patients/",
            json={"name": f"病案演示患者{self.suffix}", "id_number": f"1101011994{self.suffix[-6:]}11"},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": self.patient["id"], "doctor_id": doc["id"]},
        )
        self.encounter = self.doctor_api.call(
            "POST", "/encounters/",
            json={"registration_id": reg["id"], "diagnosis": "病案演示"},
        )

    def select_archive(self):
        self.widget._refresh()
        for row in range(self.widget.table.rowCount()):
            if self.widget.table.item(row, 1).text() == self.patient["name"]:
                self.widget.table.selectRow(row)
                self.widget._select(row, 0)
                return
        raise RuntimeError("病案列表没有本次患者")

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
            record_tab = self.tab("病案建档")
            self.scroll.verticalScrollBar().setValue(0)
            self.scene("病案室演示：为本次就诊建档", record_tab)
            self.widget.patient_id.setValue(self.patient["id"])
            self.widget.encounter_id.setValue(self.encounter["id"])
            self.widget.note.setText("门诊病案")
            self.click(record_tab, "建档")
            records = self.archive_api.call("GET", "/archive/records", params={"patient_id": self.patient["id"]})
            assert records, "病案未创建"
            record = records[0]
            assert record["status"] == "draft"
            self.scene("建档成功；未填库位直接归档应被拦截")
            self.select_archive()
            self.click(record_tab, "归档选中病案")
            assert "归档失败" in self.widget.msg.text(), self.widget.msg.text()
            self.scene("被拦截；填写库位/页数/完整性后归档")
            self.widget.location.setText(f"A区-{self.suffix[-4:]}-01")
            self.widget.pages.setValue(18)
            self.click(record_tab, "归档选中病案")
            archived = self.archive_api.call("GET", f"/archive/records/{record['id']}")
            assert archived["status"] == "archived"
            self.scene("归档上架成功；进入借阅", self.tab("借阅"))
            borrow_tab = self.tab("借阅")
            self.click(borrow_tab, "刷新可借阅病案")
            for row in range(self.widget.borrow_table.rowCount()):
                if self.widget.borrow_table.item(row, 0).text() == record["archive_no"]:
                    self.widget.borrow_table.selectRow(row)
                    self.widget._select_borrow(row, 0)
                    break
            self.widget.borrower.setText("质控科")
            self.widget.department.setText("质控")
            self.scene("选中已归档病案并借出")
            self.click(borrow_tab, "借出")
            borrowed = self.archive_api.call("GET", f"/archive/records/{record['id']}")
            assert borrowed["status"] == "borrowed", borrowed
            self.scene("借出成功；刷新后归还")
            self.click(borrow_tab, "刷新可借阅病案")
            for row in range(self.widget.borrow_table.rowCount()):
                if self.widget.borrow_table.item(row, 0).text() == record["archive_no"]:
                    self.widget.borrow_table.selectRow(row)
                    self.widget._select_borrow(row, 0)
                    break
            self.click(borrow_tab, "归还")
            returned = self.archive_api.call("GET", f"/archive/records/{record['id']}")
            assert returned["status"] == "archived", returned
            self.scene("归还成功；登记复印")
            self.widget._refresh_borrow()
            for row in range(self.widget.borrow_table.rowCount()):
                if self.widget.borrow_table.item(row, 0).text() == record["archive_no"]:
                    self.widget.borrow_table.selectRow(row)
                    self.widget._select_borrow(row, 0)
                    break
            self.widget.applicant.setText(self.patient["name"])
            self.widget.copies.setValue(1)
            self.widget.copy_contents.setText("门诊病历、检验报告")
            self.click(borrow_tab, "登记复印")
            history = self.archive_api.call("GET", f"/archive/records/{record['id']}/history")
            assert history.get("copies"), history
            self.scene("复印已登记；进入封存/启封", self.tab("封存"))
            seal_tab = self.tab("封存")
            self.click(seal_tab, "刷新已归档病案")
            for row in range(self.widget.seal_table.rowCount()):
                if self.widget.seal_table.item(row, 0).text() == record["archive_no"]:
                    self.widget.seal_table.selectRow(row)
                    self.widget._select_seal(row, 0)
                    break
            self.widget.seal_reason.setText("模拟医疗纠纷封存")
            self.widget.witness.setText("医务科")
            self.scene("选中病案并封存")
            self.click(seal_tab, "封存")
            sealed = self.archive_api.call("GET", f"/archive/records/{record['id']}")
            assert sealed["status"] == "sealed", sealed
            self.scene("封存成功；刷新后启封")
            self.click(seal_tab, "刷新已归档病案")
            for row in range(self.widget.seal_table.rowCount()):
                if self.widget.seal_table.item(row, 0).text() == record["archive_no"]:
                    self.widget.seal_table.selectRow(row)
                    self.widget._select_seal(row, 0)
                    break
            self.click(seal_tab, "启封")
            final = self.archive_api.call("GET", f"/archive/records/{record['id']}")
            assert final["status"] == "archived", final
            self.scene("病案室演示完成：建档/归档/借阅/归还/复印/封存/启封")
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
    demo = ArchiveDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
