"""管理员收费/中药页签的最小 UI 冒烟。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget

from his_client.ui.cashier import CashierWidget
from his_client.ui.tcm import TcmWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _NoopApi:
    def cashier_daily(self):
        return {
            "date": "2026-01-01", "payment_count": 0, "amount": 0.0,
            "net": 0.0, "pending_amount": 0.0, "channels": [], "shifts": [],
        }

    def list_tcm_stock_batches(self):
        return []

    def list_tcm_adjustments(self):
        return []


def test_admin_cashier_has_schedule_picker_and_merge_button(qapp):
    widget = CashierWidget(_NoopApi(), role="admin")
    assert hasattr(widget, "r_schedule_combo")
    texts = [button.text() for button in widget.findChildren(QPushButton)]
    assert "合并患者档案" in texts


def test_admin_tcm_has_adjust_approval_tab(qapp):
    widget = TcmWidget(_NoopApi(), role="admin")
    tabs = widget.findChild(QTabWidget)
    assert tabs is not None
    texts = [tabs.tabText(i) for i in range(tabs.count())]
    assert "盘点审批" in texts
    assert "批次库存" in texts
