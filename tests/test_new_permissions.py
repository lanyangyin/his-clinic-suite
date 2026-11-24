"""新增接口的权限边界回归。"""


def test_tcm_adjustments_list_requires_admin(client, auth):
    denied = client.get("/tcm/adjustments", headers=auth["cashier"])
    assert denied.status_code == 403
    allowed = client.get("/tcm/adjustments", headers=auth["admin"])
    assert allowed.status_code == 200


def test_inpatient_bill_payment_requires_cashier(client, auth):
    denied = client.post(
        "/admissions/1/bill/pay", json={"amount": 1, "method": "cash"}, headers=auth["doctor"]
    )
    assert denied.status_code == 403


def test_discharge_medication_dispense_requires_pharmacist(client, auth):
    denied = client.post(
        "/discharge-medications/1/dispense", headers=auth["nurse"]
    )
    assert denied.status_code == 403
