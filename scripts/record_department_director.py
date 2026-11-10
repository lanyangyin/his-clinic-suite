"""院长审批 + 病案销毁执行演示。

覆盖：病案室申请销毁 → 院长批准 → 病案室双人执行；院长批准采购申请。
产出：docs/科室独立演示/11_院长审批.mp4
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
from his_client.ui.director import DirectorWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "director"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "11_院长审批.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class DirectorDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("院长审批工作站 · director")
        self.director_view = DirectorWidget(ApiClient(BASE, "director", "director123"))
        self.director_window = self._wrap(self.director_view, "院长审批工作站 · director")
        self.archive_view = ArchiveWidget(ApiClient(BASE, "archive", "archive123"))
        self.archive_window = self._wrap(self.archive_view, "病案档案工作站 · archive")
        self.current = None
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
        self.archive_api = Api("archive", "archive123")
        self.warehouse_api = Api("warehouse", "warehouse123")
        self.suffix = datetime.now().strftime("%H%M%S")

    def _wrap(self, widget, title):
        window = QMainWindow()
        window.setWindowTitle(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        window.setCentralWidget(scroll)
        return window

    def wait(self, seconds=1.2):
        QTest.qWait(int(seconds * 1000))

    def activate(self, window):
        window.showMaximized()
        window.raise_()
        window.activateWindow()
        self.current = window
        self.caption.show()
        self.caption.raise_()
        self.wait(1.0)

    def scene(self, text, window=None, tab=None):
        print(f"[场景] {text}", flush=True)
        if window is not None:
            self.activate(window)
        if tab is not None:
            tabs = self._tabs()
            tabs.setCurrentWidget(tab)
        self.caption.set_text(text)
        self.caption.raise_()
        self.wait(2.6)

    def _tabs(self):
        return self.current.findChild(QTabWidget)

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
        patient = self.cashier.call(
            "POST", "/patients/",
            json={
                "name": f"院长演示患者{self.suffix}",
                "id_number": f"11010119900101{self.suffix[-4:]}",
                "phone": "13800138000",
                "privacy_consent": True,
            },
        )
        dept = self.admin.call("POST", "/departments/", json={"name": f"院长演示科{self.suffix}"})
        doc = self.admin.call(
            "POST", "/doctors/",
            json={"name": f"院长演示医生{self.suffix}", "department_id": dept["id"]},
        )
        reg = self.cashier.call(
            "POST", "/registrations/",
            json={"patient_id": patient["id"], "doctor_id": doc["id"]},
        )
        enc = self.doctor_api.call(
            "POST", "/encounters/", json={"registration_id": reg["id"]}
        )
        record = self.archive_api.call(
            "POST", "/archive/records",
            json={"patient_id": patient["id"], "encounter_id": enc["id"]},
        )
        self.archive_api.call(
            "POST", f"/archive/records/{record['id']}/archive",
            json={"storage_location": "E-02", "page_count": 8, "completeness": "complete"},
        )
        request = self.archive_api.call(
            "POST", f"/archive/records/{record['id']}/destruction-requests",
            json={"reason": "保存期满", "note": "院长演示"},
        )
        supplier = self.admin.call(
            "POST", "/suppliers/", json={"code": f"DS{self.suffix[-6:]}", "name": f"院长供应商{self.suffix}"}
        )
        drug = self.admin.call(
            "POST", "/drugs/", json={"name": f"院长采购药{self.suffix}", "base_price": 10}
        )
        purchase = self.warehouse_api.call(
            "POST", "/warehouse/purchase-requests",
            json={
                "department": "库房",
                "supplier_id": supplier["id"],
                "note": "院长演示",
                "items": [
                    {
                        "kind": "drug",
                        "drug_id": drug["id"],
                        "quantity": 10,
                        "estimated_unit_price": 9.5,
                    }
                ],
            },
        )
        record2 = self.archive_api.call(
            "POST", "/archive/records",
            json={"patient_id": patient["id"], "encounter_id": enc["id"]},
        )
        self.archive_api.call(
            "POST", f"/archive/records/{record2['id']}/archive",
            json={"storage_location": "E-03", "page_count": 5, "completeness": "complete"},
        )
        request2 = self.archive_api.call(
            "POST", f"/archive/records/{record2['id']}/destruction-requests",
            json={"reason": "重复病案", "note": "院长驳回演示"},
        )
        purchase2 = self.warehouse_api.call(
            "POST", "/warehouse/purchase-requests",
            json={
                "department": "库房",
                "supplier_id": supplier["id"],
                "note": "院长驳回演示",
                "items": [
                    {
                        "kind": "drug",
                        "drug_id": drug["id"],
                        "quantity": 20,
                        "estimated_unit_price": 9.5,
                    }
                ],
            },
        )
        return record, request, purchase, request2, purchase2

    def run(self):
        try:
            FRAME_DIR.mkdir(parents=True, exist_ok=True)
            for old in FRAME_DIR.glob("*.jpg"):
                old.unlink()
            self.timer.start(250)
            self.director_window.show()
            self.archive_window.show()
            self.caption.show()
            self.wait(1.5)
            record, archive_request, purchase, archive_request2, purchase2 = self.setup()
            self.scene("院长审批工作站：先看待审批病案销毁", self.director_window)
            self.director_view._load_archives()
            self.director_view._load_purchases()
            assert self.director_view.archive_table.rowCount() >= 1
            target = next(
                index
                for index, item in enumerate(self.director_view.archive_rows)
                if item["id"] == archive_request["id"]
            )
            self.director_view.archive_table.selectRow(target)
            self.director_view.archive_note.setText("同意，按清册执行")
            self.click(self.director_view, "批准销毁")
            approved = self.archive_api.call("GET", "/archive/destruction-requests", params={"status": "approved"})
            assert any(row["id"] == archive_request["id"] for row in approved)
            self.scene("病案销毁已批准；再看采购申请", self.director_window)
            self.director_view.findChild(QTabWidget).setCurrentIndex(1)
            self.wait(1.0)
            self.director_view._load_purchases()
            target = -1
            for row, item in enumerate(self.director_view.purchase_rows):
                if item["id"] == purchase["id"]:
                    target = row
                    break
            assert target >= 0
            self.director_view.purchase_table.selectRow(target)
            self.click(self.director_view, "批准采购")
            approved_purchase = self.warehouse_api.call("GET", f"/warehouse/purchase-requests/{purchase['id']}")
            assert approved_purchase["status"] == "approved"
            self.scene("院长批准完成；病案室执行双人销毁", self.archive_window)
            self.archive_view.findChild(QTabWidget).setCurrentIndex(2)
            self.wait(1.0)
            self.archive_view.destroy_request_id.setValue(archive_request["id"])
            self.archive_view.witness.setText("医务科")
            self.archive_view._refresh_seal()
            self.click(self.archive_view, "执行已批准销毁")
            final = self.archive_api.call("GET", f"/archive/records/{record['id']}")
            assert final["status"] == "destroyed", final
            self.scene("再演示驳回：病案销毁材料不齐", self.director_window)
            self.director_view.findChild(QTabWidget).setCurrentIndex(0)
            self.wait(1.0)
            self.director_view._load_archives()
            target = next(
                index
                for index, item in enumerate(self.director_view.archive_rows)
                if item["id"] == archive_request2["id"]
            )
            self.director_view.archive_table.selectRow(target)
            self.director_view.archive_note.setText("材料不齐，驳回")
            self.click(self.director_view, "驳回")
            rejected = self.archive_api.call(
                "GET", "/archive/destruction-requests", params={"status": "rejected"}
            )
            assert any(row["id"] == archive_request2["id"] for row in rejected)
            self.scene("病案销毁已驳回；再驳回采购申请", self.director_window)
            self.director_view.findChild(QTabWidget).setCurrentIndex(1)
            self.wait(1.0)
            self.director_view._load_purchases()
            target = next(
                index
                for index, item in enumerate(self.director_view.purchase_rows)
                if item["id"] == purchase2["id"]
            )
            self.director_view.purchase_table.selectRow(target)
            self.director_view.purchase_note.setText("预算不足，驳回")
            self.click(self.director_view, "驳回")
            rejected_purchase = self.warehouse_api.call(
                "GET", f"/warehouse/purchase-requests/{purchase2['id']}"
            )
            assert rejected_purchase["status"] == "rejected"
            self.scene("院长审批演示完成：批准/驳回、病案双人执行")
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
            for window in (self.director_window, self.archive_window):
                window.close()
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
    demo = DirectorDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
