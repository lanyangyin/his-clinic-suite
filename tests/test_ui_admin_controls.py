"""管理员收费/中药页签的最小 UI 冒烟。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget

from his_client.ui.cashier import CashierWidget
from his_client.ui.tcm import TcmWidget
from his_client.ui.inpatient import InpatientWidget


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

    def list_inpatient_admissions(self):
        return []

    def list_inpatient_orders(self, admission_id):
        return []

    def create_inpatient_admission(self, patient_id, doctor_id, bed_id):
        return {"id": 1}

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


def test_inpatient_widget_has_lists(qapp):
    widget = InpatientWidget(_NoopApi(), role="doctor")
    assert not hasattr(widget, "admit_patient")
    assert widget.admission_table.columnCount() == 5
    assert widget.order_table.columnCount() == 5
    assert widget.admission_table.rowCount() == 0


def test_admin_inpatient_has_admit_form(qapp):
    widget = InpatientWidget(_NoopApi(), role="admin")
    assert hasattr(widget, "admit_patient")
    assert widget.admit_patient.value() == 0
