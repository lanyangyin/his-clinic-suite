"""库房独立全流程慢速演示。

覆盖：新建入库单 → 验收/入库 → 药房领用申请 → 库房审核/出库
      → 总库库存核对；异常：空入库单提交拦截。
产出：docs/科室独立演示/06_库房.mp4
"""
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QScrollArea, QTabWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402
from scripts.record_ui_windows import Api, CaptionBar  # noqa: E402

BASE = "http://127.0.0.1:8001"
FRAME_DIR = ROOT / "docs" / "dept_frames" / "warehouse"
VIDEO_DIR = ROOT / "docs" / "科室独立演示"
VIDEO = VIDEO_DIR / "06_库房.mp4"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


class WarehouseDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("库房 · warehouse")
        self.widget = PharmacyWidget(ApiClient(BASE, "warehouse", "warehouse123"), role="warehouse")
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
        self.warehouse_api = Api("warehouse", "warehouse123")
        self.pharmacy_api = Api("pharmacist", "pharm123")
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
        self.supplier = self.admin.call(
            "POST", "/suppliers/",
            json={"code": f"WH{self.suffix}", "name": f"库房演示供应商{self.suffix}"},
        )
        self.drug = self.admin.call(
            "POST", "/drugs/", json={"name": f"库房演示药{self.suffix}", "base_price": 11}
        )
        self.expiry = (datetime.now().date() + timedelta(days=365)).isoformat()

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
            inbound = self.tab("入库单")
            self.scroll.verticalScrollBar().setValue(0)
            self.scene("库房演示：先验证空入库单提交", inbound)
            self.widget.in_type.setCurrentIndex(0)
            self.click(inbound, "提交入库单")
            assert "请先添加" in self.widget.in_msg.text(), self.widget.in_msg.text()
            self.scene("空单被拦截；选择药品并添加入库行")
            self.widget.in_type.setCurrentIndex(0)
            self.click(inbound, "刷新供应商")
            for index in range(self.widget.in_supplier.count()):
                if self.supplier["name"] in self.widget.in_supplier.itemText(index):
                    self.widget.in_supplier.setCurrentIndex(index)
                    break
            self.widget.in_drug_source.setCurrentIndex(1)
            self.click(inbound, "刷新药品")
            for index in range(self.widget.in_drug.count()):
                if self.drug["name"] in self.widget.in_drug.itemText(index):
                    self.widget.in_drug.setCurrentIndex(index)
                    break
            self.widget.in_batch.setText(f"WH-{self.suffix}")
            self.widget.in_expiry.setText(self.expiry)
            self.widget.in_qty.setValue(10)
            self.widget.in_price.setText("11.00")
            self.click(inbound, "添加药品行")
            self.widget.in_msg.setText("")
            self.scene("提交入库单")
            self.click(inbound, "提交入库单")
            orders = self.warehouse_api.call("GET", "/inbound/orders")
            order = next(row for row in orders if row["order_type"] == "drug" and row["items"])
            order_no = order["order_no"]
            self.click(inbound, "刷新入库单")
            for row in range(self.widget.order_table.rowCount()):
                if self.widget.order_table.item(row, 0).text() == order_no:
                    self.widget.order_table.selectRow(row)
                    self.widget._select_order(row, 0)
                    break
            self.scene("选中入库单，全部合格验收")
            self.click(inbound, "全部合格验收")
            self.scene("验收入库，总库库存 10 盒")
            self.click(inbound, "入库")
            stock = self.warehouse_api.call("GET", f"/warehouse/stocks?drug_id={self.drug['id']}")
            assert sum(row["quantity"] for row in stock) == 10
            self.scene("入库完成；药房发起领用申请（镜头外）")
            request = self.pharmacy_api.call(
                "POST", "/warehouse/outbound-orders",
                json={
                    "outbound_type": "requisition", "target_type": "pharmacy", "target_name": "药房",
                    "items": [{"kind": "drug", "drug_id": self.drug["id"], "batch_no": f"WH-{self.suffix}", "quantity": 2}],
                },
            )
            handle = self.tab("出库处理")
            self.scene("库房审核领用申请", handle)
            self.click(handle, "刷新出库单")
            target = -1
            for row in range(self.widget.handle_table.rowCount()):
                if self.widget.handle_table.item(row, 0).text() == request["outbound_no"]:
                    target = row
                    break
            assert target >= 0, "出库列表没有本次申请"
            self.widget.handle_table.selectRow(target)
            self.widget._select_handle_order(target, 0)
            self.click(handle, "审核通过")
            self.scene("审核通过，全部出库给药房")
            self.click(handle, "全部出库")
            pharmacy_stock = self.pharmacy_api.call(
                "GET", f"/pharmacy/stocks?drug_id={self.drug['id']}"
            )
            assert sum(row["quantity"] for row in pharmacy_stock) == 2
            self.scene("出库完成；查看总库库存")
            stock_tab = self.tab("总库库存")
            self.click(stock_tab, "刷新总库库存")
            self.scene("库房演示完成：入库/验收/审核/出库/库存")
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
    demo = WarehouseDemo()
    QTimer.singleShot(800, demo.run)
    app.exec()
    ok = encode()
    print("结果：", "通过" if demo.success else f"失败 {demo.error}")
    return 0 if ok and demo.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
