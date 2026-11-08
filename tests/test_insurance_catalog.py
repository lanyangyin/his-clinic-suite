import io

import pytest
from openpyxl import Workbook

from app.modules.insurance_catalog import service as catalog_service

CSV_HEADERS = "国家医保药品代码,药品名称,剂型,规格,生产厂家,单位,医保类别,限定支付范围,批准文号\n"
CSV_ROWS = (
    "XA01ABC001,阿莫西林胶囊,胶囊剂,0.25g*24粒,华北制药,盒,乙,限口服,国药准字H13023964\n"
    "XA01ABC002,布洛芬片,片剂,0.2g*20片,中美史克,盒,甲,,国药准字H10900089\n"
)


def import_csv(client, auth, content: str, filename="catalog.csv"):
    return client.post(
        "/insurance/catalog/import",
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
        headers=auth["admin"],
    )


def test_catalog_csv_import_search_versions(client, auth):
    r = import_csv(client, auth, CSV_HEADERS + CSV_ROWS)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["inserted"] == 2
    assert body["row_count"] == 2
    assert body["version"] == "V0001"

    rows = client.get("/insurance/catalog/search?q=阿莫").json()
    assert len(rows) == 1
    assert rows[0]["name"] == "阿莫西林胶囊"
    assert rows[0]["category"] == "乙"

    by_code = client.get("/insurance/catalog/XA01ABC002")
    assert by_code.status_code == 200
    assert by_code.json()["category"] == "甲"

    versions = client.get("/insurance/catalog/versions").json()
    assert len(versions) == 1
    assert versions[0]["source"] == "manual"


def test_catalog_reimport_unchanged_and_update(client, auth):
    content = CSV_HEADERS + CSV_ROWS
    import_csv(client, auth, content)

    same = import_csv(client, auth, content).json()
    assert same["status"] == "unchanged"
    assert same["version"] == "V0001"

    changed = content + "XA01ABC003,维生素C片,片剂,100mg*100片,东北制药,瓶,乙,,国药准字H21020001\n"
    result = import_csv(client, auth, changed).json()
    assert result["status"] == "created"
    assert result["version"] == "V0002"
    assert result["inserted"] == 1
    assert len(client.get("/insurance/catalog/search?q=维生素C").json()) == 1


def test_catalog_xlsx_import(client, auth):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["国家医保药品代码", "药品名称", "剂型", "规格", "生产厂家", "单位", "医保类别"])
    sheet.append(["XA01XYZ001", "头孢克肟胶囊", "胶囊剂", "0.1g*6粒", "广州白云山", "盒", "乙"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    r = client.post(
        "/insurance/catalog/import",
        files={"file": ("catalog.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth["admin"],
    )
    assert r.status_code == 200
    assert r.json()["inserted"] == 1
    assert client.get("/insurance/catalog/search?q=头孢克肟").json()[0]["dosage_form"] == "胶囊剂"


def test_catalog_sync_from_url(client, auth, monkeypatch):
    class FakeResponse:
        content = (CSV_HEADERS + CSV_ROWS).encode("utf-8")

        def raise_for_status(self):
            return None

    monkeypatch.setattr(catalog_service.requests, "get", lambda url, timeout=30: FakeResponse())

    r = client.post(
        "/insurance/catalog/sync",
        json={"url": "http://example.com/insurance_catalog.csv"},
        headers=auth["admin"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "created"
    assert r.json()["inserted"] == 2
    versions = client.get("/insurance/catalog/versions").json()
    assert versions[0]["source"] == "auto"


def test_catalog_permissions_and_errors(client, auth):
    r = client.post(
        "/insurance/catalog/import",
        files={"file": ("catalog.csv", b"x", "text/csv")},
        headers=auth["cashier"],
    )
    assert r.status_code == 403

    empty = client.post(
        "/insurance/catalog/import",
        files={"file": ("empty.csv", b"", "text/csv")},
        headers=auth["admin"],
    )
    assert empty.status_code == 400
