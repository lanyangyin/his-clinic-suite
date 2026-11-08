HL7_MESSAGE = (
    "MSH|^~\\&|EMR|HOSPITAL|HIS|HIS|20261108120000||ADT^A01|MSG0001|P|2.4\r"
    "PID|1||110101199001011234^张三||19800101|M\r"
)


def test_fhir_patient_resource(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234", "phone": "13800138000"},
        headers=auth["cashier"],
    ).json()
    r = client.get(f"/integration/fhir/Patient/{patient['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["resourceType"] == "Patient"
    assert body["id"] == str(patient["id"])
    values = {item["value"] for item in body["identifier"]}
    assert "110101199001011234" in values
    assert body["name"][0]["family"] == "张三"
    assert body["telecom"][0]["value"] == "13800138000"
    assert body["active"] is True


def test_fhir_patient_missing(client):
    r = client.get("/integration/fhir/Patient/999")
    assert r.status_code == 404


def test_hl7_adt_creates_patient(client):
    r = client.post("/integration/hl7/adt", json={"message": HL7_MESSAGE})
    assert r.status_code == 201
    body = r.json()
    assert body["created"] is True
    # 通过 FHIR 查询验证建档内容
    fhir = client.get(f"/integration/fhir/Patient/{body['patient_id']}").json()
    assert fhir["name"][0]["family"] == "张三"


def test_hl7_adt_idempotent(client):
    first = client.post("/integration/hl7/adt", json={"message": HL7_MESSAGE}).json()
    second = client.post("/integration/hl7/adt", json={"message": HL7_MESSAGE}).json()
    assert first["created"] is True
    assert second["created"] is False
    assert first["patient_id"] == second["patient_id"]


def test_hl7_adt_missing_pid(client):
    r = client.post(
        "/integration/hl7/adt",
        json={"message": "MSH|^~\\&|EMR|HOSPITAL|HIS|HIS|20261108120000||ADT^A01|MSG0002|P|2.4"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "消息缺少 PID 段"


def test_hl7_adt_bad_pid(client):
    r = client.post(
        "/integration/hl7/adt", json={"message": "PID|1|||"}
    )
    assert r.status_code == 400


def test_integration_logs(client, auth):
    client.post("/integration/hl7/adt", json={"message": HL7_MESSAGE})
    client.get("/integration/fhir/Patient/1")
    r = client.get("/integration/logs", headers=auth["admin"])
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) >= 1
    assert logs[0]["protocol"] == "hl7"
    assert logs[0]["direction"] == "in"


def test_logs_require_admin(client, auth):
    assert client.get("/integration/logs", headers=auth["doctor"]).status_code == 403
    assert client.get("/integration/logs").status_code == 401
