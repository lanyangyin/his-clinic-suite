"""真实人事窗口：入职 + 同时建账号 + 离职，保存截图。"""
import os, sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from his_client.api import ApiClient
from his_client.ui.hr import HrWidget

OUT=Path('docs/gui_evidence'); OUT.mkdir(parents=True,exist_ok=True)

def click(root,text):
    for b in root.findChildren(QPushButton):
        if b.text().strip()==text and b.isVisible() and b.isEnabled():
            QTest.mouseClick(b,Qt.LeftButton); return
    raise AssertionError(f"找不到 {text}")

def main():
    app=QApplication.instance() or QApplication([])
    admin=ApiClient('http://127.0.0.1:8001','admin','admin123')
    hr=ApiClient('http://127.0.0.1:8001','hr_gui','hr123')
    stamp=str(int(time.time()))
    widget=HrWidget(hr); widget.show(); app.processEvents()
    widget.emp_no.setText(f'E{stamp[-7:]}'); widget.emp_name.setText(f'入职点击{stamp[-5:]}')
    widget.emp_role.setCurrentIndex(0)
    widget.emp_account.setChecked(True)
    widget.emp_username.setText(f'hrflow{stamp[-6:]}')
    widget.emp_password.setText('Pass1234')
    click(widget,'新增员工'); app.processEvents()
    widget.grab().save(str(OUT/'hr_full_after_onboard.png'))
    rows=admin._request('GET','/hr/employees/')
    employee=next(r for r in rows if r['employee_no']==f'E{stamp[-7:]}')
    user=admin._request('GET','/users/')
    account=next(u for u in user if u['username']==f'hrflow{stamp[-6:]}')
    assert employee['status']=='active'
    widget._load_employees(); app.processEvents()
    row=next(i for i,x in enumerate(widget.employees) if x['id']==employee['id'])
    widget.emp_table.selectRow(row)
    with patch('his_client.ui.hr.QMessageBox.question', return_value=QMessageBox.Yes):
        click(widget,'办理离职')
    app.processEvents()
    widget.grab().save(str(OUT/'hr_full_after_resign.png'))
    emp=admin._request('GET',f"/hr/employees/{employee['id']}")
    usr=admin._request('GET',f"/users/{account['id']}")
    assert emp['status']=='resigned', emp
    assert usr['is_active'] is False, usr
    print(f"EMP={employee['id']} USER={account['id']} HR_FULL_CLICK=OK")
    widget.close(); widget.deleteLater(); app.processEvents()
    return 0
if __name__=='__main__': sys.exit(main())
