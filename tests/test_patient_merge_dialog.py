"""患者合并对话框：管理员/院长入口的最小 UI 冒烟。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from his_client.ui.patient_merge import PatientMergeDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _Api:
    def merge_patient_direct(self, *args, **kwargs):
        return {"id": 1}

    def create_patient_merge_request(self, *args, **kwargs):
        return {"id": 1}


def test_merge_dialog_prefills_source(qapp):
    dialog = PatientMergeDialog(_Api(), "admin", source_id=12)
    assert dialog.source.value() == 12
    assert dialog.role == "admin"
    assert dialog.windowTitle() == "患者档案合并"


def test_merge_dialog_requires_reason(qapp):
    dialog = PatientMergeDialog(_Api(), "director", source_id=12)
    dialog.target.setValue(13)
    dialog._submit()
    assert "原因" in dialog.msg.text()
