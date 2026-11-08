import shutil
from pathlib import Path

import pytest
import requests

from his_client.api import ApiClient, ApiError
from his_client.config import load_config, parse_config


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content_type="application/json"):
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": content_type}
        self.reason = "Bad Request"

    def json(self):
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []
        self.headers = {}
        self.auth = None

    def request(self, method, url, timeout=None, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_me_success_sets_basic_auth():
    session = FakeSession(
        [FakeResponse(200, {"id": 1, "username": "admin", "role": "admin", "display_name": "管理员"})]
    )
    client = ApiClient("http://127.0.0.1:8000", "admin", "admin123", session=session)
    user = client.me()
    assert user["username"] == "admin"
    assert session.auth == ("admin", "admin123")
    assert session.calls[0][0] == "GET"
    assert session.calls[0][1] == "http://127.0.0.1:8000/auth/me"


def test_error_detail_propagated():
    session = FakeSession([FakeResponse(400, {"detail": "该就诊已收费"})])
    client = ApiClient("http://x", "cashier", "pw", session=session)
    with pytest.raises(ApiError) as exc:
        client.create_payment(3)
    assert exc.value.status_code == 400
    assert exc.value.detail == "该就诊已收费"
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "http://x/payments/"
    assert kwargs["json"] == {"encounter_id": 3}


def test_non_json_error_uses_reason():
    session = FakeSession([FakeResponse(500, None, content_type="text/html")])
    client = ApiClient("http://x", session=session)
    with pytest.raises(ApiError) as exc:
        client.get_charges(1)
    assert exc.value.status_code == 500


def test_connection_error_mapped():
    session = FakeSession([requests.ConnectionError("refused")])
    client = ApiClient("http://x", "u", "p", session=session)
    with pytest.raises(ApiError) as exc:
        client.me()
    assert exc.value.status_code == 0
    assert "无法连接服务器" in exc.value.detail


def test_create_patient_payload():
    session = FakeSession([FakeResponse(201, {"id": 9, "name": "张三", "id_number": "110101199001011234"})])
    client = ApiClient("http://x", "cashier", "pw", session=session)
    patient = client.create_patient("张三", "110101199001011234", "")
    assert patient["id"] == 9
    assert session.calls[0][2]["json"] == {
        "name": "张三",
        "id_number": "110101199001011234",
        "phone": None,
    }


def test_print_urls():
    client = ApiClient("http://192.168.1.5:8000/", session=FakeSession())
    assert client.prescription_print_url(7) == "http://192.168.1.5:8000/print/prescription/7"
    assert client.receipt_print_url(8) == "http://192.168.1.5:8000/print/receipt/8"


def _work_dir() -> Path:
    """项目内临时目录（Windows 系统临时目录在沙箱下可能无权限）。"""
    path = Path("tmp_client_test")
    path.mkdir(exist_ok=True)
    return path


def test_medical_record_and_lab_methods():
    session = FakeSession(
        [
            FakeResponse(201, {"id": 1}),
            FakeResponse(200, [{"id": 1, "name": "血常规", "price": 20.0}]),
            FakeResponse(201, {"id": 2, "item_name": "血常规"}),
        ]
    )
    client = ApiClient("http://x", "doctor", "pw", session=session)
    client.create_medical_record(5, {"chief_complaint": "发热"})
    items = client.list_lab_items()
    client.create_lab_request(5, 1)
    assert items[0]["name"] == "血常规"
    assert session.calls[0][1] == "http://x/encounters/5/medical-record"
    assert session.calls[0][2]["json"] == {"chief_complaint": "发热"}
    assert session.calls[2][1] == "http://x/lab/encounters/5/lab-requests"


def test_pharmacy_and_nurse_methods():
    session = FakeSession(
        [
            FakeResponse(200, [{"id": 1, "drug_id": 2}]),
            FakeResponse(201, {"id": 3, "batch_no": "B1"}),
            FakeResponse(200, [{"id": 4, "status": "waiting"}]),
        ]
    )
    client = ApiClient("http://x", "pharmacist", "pw", session=session)
    stocks = client.list_stocks()
    client.stock_in({"drug_id": 2, "batch_no": "B1", "expiry": "2027-01-01", "quantity": 10})
    queue = client.triage_queue()
    assert stocks and queue
    assert session.calls[0][1] == "http://x/pharmacy/stocks"
    assert session.calls[1][1] == "http://x/pharmacy/stock-in"
    assert session.calls[2][1] == "http://x/triage/queue"


def test_treatment_pending_list():
    session = FakeSession([FakeResponse(200, [])])
    client = ApiClient("http://x", "nurse", "pw", session=session)
    client.list_pending_treatments()
    assert session.calls[0][1] == "http://x/treatments/"
    assert session.calls[0][2]["params"] == {"status": "pending"}

    work = _work_dir()
    try:
        config_file = work / "config.ini"
        config_file.write_text(
            "[server]\nurl = http://192.168.1.5:8000\n[client]\ntimeout = 20\nprinter = 小票打印机\n",
            encoding="utf-8",
        )
        config = parse_config(config_file)
        assert config.server_url == "http://192.168.1.5:8000"
        assert config.timeout == 20
        assert config.printer == "小票打印机"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_local_override(monkeypatch):
    work = _work_dir()
    try:
        (work / "config.ini").write_text(
            "[server]\nurl = http://10.0.0.1:8000\n[client]\ntimeout = 30\n", encoding="utf-8"
        )
        (work / "config.local.ini").write_text(
            "[server]\nurl = http://127.0.0.1:8001\n", encoding="utf-8"
        )
        monkeypatch.chdir(work)
        config = load_config()
        assert config.server_url == "http://127.0.0.1:8001"
        assert config.timeout == 30  # 未覆盖的项保持主配置
    finally:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        shutil.rmtree(work, ignore_errors=True)


def test_load_config_falls_back_to_defaults(monkeypatch):
    work = _work_dir()
    try:
        monkeypatch.chdir(work)
        monkeypatch.delenv("HIS_CLIENT_CONFIG", raising=False)
        config = load_config()
        assert config.server_url.startswith("http")
        assert config.timeout == 10
    finally:
        monkeypatch.chdir(Path(__file__).resolve().parent.parent)
        shutil.rmtree(work, ignore_errors=True)
