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


def test_new_admin_pages_require_login(client):
    for path in (
        "/admin/finance",
        "/admin/refund-export-templates",
        "/admin/tcm-adjustments",
        "/admin/inpatient",
        "/admin/notification-templates",
    ):
        response = client.get(path, follow_redirects=False)
        assert response.status_code in (302, 303), path
