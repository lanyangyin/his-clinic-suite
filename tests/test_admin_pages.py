

def test_dashboard_and_print_center(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    dashboard = client.get("/admin/dashboard")
    assert dashboard.status_code == 200
    assert "今日运营看板" in dashboard.text
    center = client.get("/admin/print-center")
    assert center.status_code == 200
    assert "打印中心" in center.text
