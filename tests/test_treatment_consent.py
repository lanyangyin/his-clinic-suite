def setup_case(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "同意书患者", "id_number": "110101199001013333"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "同意书科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "同意书医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    case = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": enc["id"],
            "procedure_name": "换药",
        },
        headers=auth["treatment"],
    ).json()
    return patient, enc, case


def test_consent_requires_signer_and_signature(client, auth):
    patient, enc, case = setup_case(client, auth)
    no_signer = client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True},
        headers=auth["treatment"],
    )
    assert no_signer.status_code == 400
    assert "签署人" in no_signer.json()["detail"]

    no_signature = client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={
            "consent": True,
            "consent_signer": patient["name"],
            "consent_relation": "本人",
        },
        headers=auth["treatment"],
    )
    assert no_signature.status_code == 400
    assert "签名" in no_signature.json()["detail"]


def test_consent_signature_upload_and_start(client, auth):
    patient, enc, case = setup_case(client, auth)
    upload = client.post(
        f"/treatment-room/cases/{case['id']}/consent-signature",
        files={"file": ("consent.png", b"\x89PNG\r\n\x1a\n" + b"demo", "image/png")},
        headers=auth["treatment"],
    )
    assert upload.status_code == 200, upload.text
    path = upload.json()["signature_path"]
    assert path.startswith("data/treatment_consents/")

    started = client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={
            "consent": True,
            "consent_signer": patient["name"],
            "consent_relation": "本人",
            "consent_signature_path": path,
        },
        headers=auth["treatment"],
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["consent"] is True
    assert body["consent_signer"] == patient["name"]
    assert body["consent_signature_path"] == path
    assert body["consent_signed_at"] is not None
    assert body["consent_version"] == "v1"


def test_consent_rejects_non_image(client, auth):
    patient, enc, case = setup_case(client, auth)
    response = client.post(
        f"/treatment-room/cases/{case['id']}/consent-signature",
        files={"file": ("consent.txt", b"not image", "text/plain")},
        headers=auth["treatment"],
    )
    assert response.status_code == 400
