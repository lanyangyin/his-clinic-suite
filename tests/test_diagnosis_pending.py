"""诊断必须先完成病史/查体；结果未回时可暂记待查。"""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from his_client.ui.diagnosis_editor import DiagnosisEditor
from his_client.ui.doctor import DoctorWidget  # noqa: F401


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_pending_diagnosis_is_primary_and_idempotent(qapp):
    editor = DiagnosisEditor()
    editor.add_pending_diagnosis()
    items = editor.get_items()
    assert items[0]["diagnosis"] == "待查"
    assert "回报" in items[0]["note"]
    editor.add_pending_diagnosis()
    assert len(editor.get_items()) == 1


def test_record_page_places_diagnosis_after_exam_before_treatment():
    text = Path("his_client/ui/doctor.py").read_text(encoding="utf-8")
    assert '"treatment_advice": (5, 0)' in text
    assert "grid.addWidget(diagnosis_box, 4, 0, 1, 2)" in text
    # 诊断框必须由病史/查体网格承载，而不是布局顶部
    assert "diagnosis_layout = QVBoxLayout(diagnosis_box)" in text
