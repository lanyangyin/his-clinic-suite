from concurrent.futures import ThreadPoolExecutor

from app.modules.idempotency import service as idempotency


def make_patient_payload(id_number="110101199001011234"):
    return {"name": "张三", "id_number": id_number}


def test_replay_returns_cached_response(client, auth):
    payload = make_patient_payload()
    first = client.post(
        "/patients/", json=payload,
        headers={**auth["cashier"], "Idempotency-Key": "key-001"},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        "/patients/", json=payload,
        headers={**auth["cashier"], "Idempotency-Key": "key-001"},
    )
    assert second.status_code == 201
    assert second.json()["id"] == first_id
    assert second.headers.get("Idempotent-Replayed") == "true"

    # 只创建了一个患者
    assert len(client.get("/patients/").json()) == 1


def test_without_key_no_dedup(client, auth):
    payload = make_patient_payload("110101199501011234")
    client.post("/patients/", json=payload, headers=auth["cashier"])
    client.post("/patients/", json=payload, headers=auth["cashier"])
    # 患者按身份证查重只会有 1 条，换挂号接口验证"无 key 不缓存"
    patient = client.get("/patients/").json()[0]
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    r1 = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    )
    r2 = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    )
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
    assert len(client.get("/registrations/").json()) == 2


def test_same_key_different_endpoints_isolated(client, auth):
    payload = make_patient_payload()
    r1 = client.post(
        "/patients/", json=payload,
        headers={**auth["cashier"], "Idempotency-Key": "shared-key"},
    )
    assert r1.status_code == 201
    # 同一 key 用在别的接口：互不干扰（endpoint 维度隔离）
    department = client.post(
        "/departments/", json={"name": "内科"},
        headers={**auth["admin"], "Idempotency-Key": "shared-key"},
    )
    assert department.status_code == 201


def test_business_error_is_cached(client, auth):
    # 不存在的患者挂号 → 404；同 key 重放应返回同样的 404（而不是重新执行）
    headers = {**auth["cashier"], "Idempotency-Key": "error-key"}
    first = client.post(
        "/registrations/", json={"patient_id": 999, "doctor_id": 1}, headers=headers
    )
    assert first.status_code == 404
    second = client.post(
        "/registrations/", json={"patient_id": 999, "doctor_id": 1}, headers=headers
    )
    assert second.status_code == 404
    assert second.headers.get("Idempotent-Replayed") == "true"


def test_reserve_is_atomic_under_concurrency():
    """同 key 并发占位：唯一约束保证只有 1 个成功。"""

    def worker(_):
        return idempotency.reserve("race-key", "POST /patients/")

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(worker, range(10)))

    assert sum(1 for r in results if r) == 1
    assert sum(1 for r in results if not r) == 9

    # 清理占位，避免影响后续用例
    idempotency.release("race-key", "POST /patients/")


def test_processing_key_returns_409(client, auth):
    """占位存在但未完成（模拟处理中的请求）→ 409。"""
    idempotency.reserve("slow-key", "POST /patients/")
    r = client.post(
        "/patients/", json=make_patient_payload(),
        headers={**auth["cashier"], "Idempotency-Key": "slow-key"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "请求正在处理中，请稍后重试"
    idempotency.release("slow-key", "POST /patients/")


def test_get_ignores_idempotency_key(client, auth):
    patient = client.post(
        "/patients/", json=make_patient_payload(), headers=auth["cashier"]
    ).json()
    header = {"Idempotency-Key": "get-key"}
    r1 = client.get(f"/patients/{patient['id']}", headers=header)
    r2 = client.get(f"/patients/{patient['id']}", headers=header)
    assert r1.status_code == r2.status_code == 200
    assert r2.headers.get("Idempotent-Replayed") is None
