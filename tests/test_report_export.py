"""运营报表 Excel 导出。"""
from io import BytesIO

from openpyxl import load_workbook


def _seed(client, auth):
    dept = client.post(
        "/departments/", json={"name": "导出内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "导出医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": "导出患者", "id_number": "110101199001019999"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "导出诊断"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "导出药品", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )


def test_executive_excel_export(client, auth):
    _seed(client, auth)
    response = client.get(
        "/bi/executive/export.xlsx", headers=auth["admin"]
    )
    assert response.status_code == 200, response.text
    assert "spreadsheetml" in response.headers["content-type"]
    workbook = load_workbook(BytesIO(response.content))
    assert "运营概览" in workbook.sheetnames
    assert "科室收入" in workbook.sheetnames
    assert "收入趋势" in workbook.sheetnames
    overview = workbook["运营概览"]
    values = [row[0] for row in overview.iter_rows(values_only=True)]
    assert "门诊人次" in values
    assert "医疗收入" in values


def test_department_revenue_excel_export(client, auth):
    _seed(client, auth)
    response = client.get(
        "/reports/departments/revenue/export.xlsx", headers=auth["admin"]
    )
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content))
    assert workbook["科室收入"].max_row >= 2
    assert workbook["科室收入"]["A2"].value == "导出内科"


def test_export_permissions(client, auth):
    assert (
        client.get("/bi/executive/export.xlsx", headers=auth["cashier"]).status_code
        == 403
    )
    assert (
        client.get(
            "/reports/departments/revenue/export.xlsx", headers=auth["cashier"]
        ).status_code
        == 403
    )
