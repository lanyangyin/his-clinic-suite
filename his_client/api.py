"""REST API 封装：客户端所有服务端交互都走这里（便于测试与复用）。"""
from __future__ import annotations

import requests
from urllib.parse import quote


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ApiClient:
    """HTTP Basic 认证的 API 客户端；session 可注入以便测试。"""

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        session: requests.Session | None = None,
        timeout: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if username is not None:
            self.set_credentials(username, password or "")

    def set_credentials(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.session.auth = (username, password)

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method, url, timeout=self.timeout, **kwargs
            )
        except requests.RequestException as e:
            raise ApiError(0, f"无法连接服务器：{e}") from e

        if response.status_code >= 400:
            detail = response.reason or "请求失败"
            try:
                payload = response.json()
                if isinstance(payload, dict) and payload.get("detail"):
                    detail = str(payload["detail"])
            except ValueError:
                pass
            raise ApiError(response.status_code, detail)

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text

    # ---- 登录 / 基础信息 ----
    def version(self) -> dict:
        return self._request("GET", "/version")

    def me(self) -> dict:
        return self._request("GET", "/auth/me")

    # ---- 基础数据 ----
    def list_doctors(self) -> list:
        return self._request("GET", "/doctors/")

    def list_drugs(self) -> list:
        return self._request("GET", "/drugs/")

    def list_schedules(self, doctor_id: int) -> list:
        return self._request("GET", f"/doctors/{doctor_id}/schedules")

    def list_charge_items(self, category: str | None = None) -> list:
        params = {"category": category} if category else {}
        return self._request("GET", "/charges/items/", params=params)

    # ---- 患者 ----
    def list_patients(
        self, name: str | None = None, id_number: str | None = None, phone: str | None = None
    ) -> list:
        params = {}
        if name:
            params["name"] = name
        if id_number:
            params["id_number"] = id_number
        if phone:
            params["phone"] = phone
        return self._request("GET", "/patients/", params=params)

    def get_patient(self, patient_id: int) -> dict:
        return self._request("GET", f"/patients/{patient_id}")

    def get_registration(self, registration_id: int) -> dict:
        return self._request("GET", f"/registrations/{registration_id}")

    def get_encounter(self, encounter_id: int) -> dict:
        return self._request("GET", f"/encounters/{encounter_id}")

    def get_patient_by_card(self, card_uid: str) -> dict:
        return self._request("GET", f"/patients/by-card/{card_uid}")

    def issue_patient_card(self, patient_id: int, card_uid: str, note: str = "") -> dict:
        return self._request(
            "POST",
            f"/patients/{patient_id}/cards",
            json={"card_uid": card_uid, "note": note},
        )

    def list_patient_cards(self, patient_id: int) -> list:
        return self._request("GET", f"/patients/{patient_id}/cards")

    def mark_patient_card_lost(self, patient_id: int, card_id: int) -> dict:
        return self._request(
            "POST", f"/patients/{patient_id}/cards/{card_id}/lost"
        )

    def reissue_patient_card(self, patient_id: int, card_uid: str, note: str = "") -> dict:
        return self._request(
            "POST",
            f"/patients/{patient_id}/cards/reissue",
            json={"card_uid": card_uid, "note": note},
        )

    def check_patient_duplicates(
        self, name: str = "", id_number: str = "", phone: str = ""
    ) -> dict:
        return self._request(
            "GET",
            "/patients/duplicates",
            params={"name": name, "id_number": id_number, "phone": phone},
        )

    def create_patient(
        self,
        name: str | None = None,
        id_number: str | None = None,
        phone: str = "",
        payload: dict | None = None,
        **fields,
    ) -> dict:
        body = dict(payload or {})
        if name is not None:
            body.update({"name": name, "id_number": id_number, "phone": phone or None})
        body.update(fields)
        return self._request("POST", "/patients/", json=body)

    def update_patient(self, patient_id: int, payload: dict) -> dict:
        return self._request("PUT", f"/patients/{patient_id}", json=payload)

    # ---- 挂号 / 就诊 ----
    def create_registration(
        self, patient_id: int, doctor_id: int, schedule_id: int | None = None
    ) -> dict:
        payload = {"patient_id": patient_id, "doctor_id": doctor_id}
        if schedule_id:
            payload["schedule_id"] = schedule_id
        return self._request("POST", "/registrations/", json=payload)

    def list_registrations(
        self, patient_id: int | None = None, status: str | None = None
    ) -> list:
        params = {}
        if patient_id:
            params["patient_id"] = patient_id
        if status:
            params["status"] = status
        return self._request("GET", "/registrations/", params=params)

    def list_encounters(self, patient_id: int | None = None) -> list:
        params = {"patient_id": patient_id} if patient_id else {}
        return self._request("GET", "/encounters/", params=params)

    def doctor_worklist(self) -> list:
        return self._request("GET", "/encounters/worklist")

    def encounter_summary(self, encounter_id: int) -> dict:
        return self._request("GET", f"/encounters/{encounter_id}/summary")

    def create_encounter(
        self, registration_id: int, diagnosis: str = "", diagnosis_code: str = ""
    ) -> dict:
        return self._request(
            "POST",
            "/encounters/",
            json={
                "registration_id": registration_id,
                "diagnosis": diagnosis,
                "diagnosis_code": diagnosis_code,
            },
        )

    def update_encounter_diagnosis(
        self, encounter_id: int, diagnosis_code: str, diagnosis: str = ""
    ) -> dict:
        return self._request(
            "PUT",
            f"/encounters/{encounter_id}/diagnosis",
            json={"diagnosis_code": diagnosis_code, "diagnosis": diagnosis},
        )

    def list_diagnoses(self) -> list:
        return self._request(
            "GET",
            "/dict/diagnosis_icd10/entries",
            params={"active_only": "true"},
        )

    # ---- 病历 ----
    def get_medical_record(self, encounter_id: int) -> dict:
        return self._request("GET", f"/encounters/{encounter_id}/medical-record")

    def get_patient_history(self, patient_id: int) -> dict:
        return self._request("GET", f"/patients/{patient_id}/history")

    def patient_profile(self, patient_id: int) -> dict:
        return self._request("GET", f"/patients/{patient_id}/profile")

    def create_medical_record(self, encounter_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/encounters/{encounter_id}/medical-record", json=payload
        )

    def update_medical_record(self, encounter_id: int, payload: dict) -> dict:
        return self._request(
            "PUT", f"/encounters/{encounter_id}/medical-record", json=payload
        )

    def sign_medical_record(self, encounter_id: int) -> dict:
        return self._request("POST", f"/encounters/{encounter_id}/medical-record/sign")

    def medical_record_quality(self, encounter_id: int) -> dict:
        return self._request("GET", f"/encounters/{encounter_id}/medical-record/quality")

    # ---- 处方 ----
    def list_prescriptions(self, encounter_id: int) -> list:
        return self._request("GET", f"/encounters/{encounter_id}/prescriptions")

    def add_prescription(self, encounter_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/encounters/{encounter_id}/prescriptions", json=payload
        )

    # ---- 检验 / 检查 ----
    def list_lab_items(self) -> list:
        return self._request("GET", "/lab/items/")

    def create_lab_request(self, encounter_id: int, item_id: int) -> dict:
        return self._request(
            "POST",
            f"/lab/encounters/{encounter_id}/lab-requests",
            json={"item_id": item_id},
        )

    def list_lab_requests(self, encounter_id: int) -> list:
        return self._request("GET", f"/lab/encounters/{encounter_id}/lab-requests")

    def lab_worklist(self, status: str | None = None, priority: str | None = None) -> list:
        params = {}
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        return self._request("GET", "/lab/worklist", params=params)

    def collect_lab(self, request_id: int) -> dict:
        return self._request("POST", f"/lab/requests/{request_id}/collect", json={})

    def receive_lab(self, request_id: int) -> dict:
        return self._request("POST", f"/lab/requests/{request_id}/receive")

    def reject_lab(self, request_id: int, reason: str) -> dict:
        return self._request(
            "POST", f"/lab/requests/{request_id}/reject", json={"reason": reason}
        )

    def start_lab(self, request_id: int) -> dict:
        return self._request("POST", f"/lab/requests/{request_id}/start")

    def report_lab(self, request_id: int, payload: dict) -> dict:
        return self._request("POST", f"/lab/requests/{request_id}/report", json=payload)

    def review_lab(self, request_id: int) -> dict:
        return self._request("POST", f"/lab/requests/{request_id}/review")

    def critical_lab(self, request_id: int, note: str, notified_to: str) -> dict:
        return self._request(
            "POST",
            f"/lab/requests/{request_id}/critical",
            json={"note": note, "notified_to": notified_to},
        )

    def critical_alerts(self) -> list:
        return self._request("GET", "/lab/critical-alerts")

    def ack_critical_lab(self, request_id: int, note: str = "") -> dict:
        return self._request(
            "POST",
            f"/lab/requests/{request_id}/critical-ack",
            json={"note": note},
        )

    # ---- 病案档案 ----
    def list_archive_records(self, **params) -> list:
        return self._request("GET", "/archive/records", params=params)

    def create_archive_record(self, payload: dict) -> dict:
        return self._request("POST", "/archive/records", json=payload)

    def archive_record(self, record_id: int, payload: dict) -> dict:
        return self._request("POST", f"/archive/records/{record_id}/archive", json=payload)

    def borrow_archive(self, record_id: int, payload: dict) -> dict:
        return self._request("POST", f"/archive/records/{record_id}/borrow", json=payload)

    def return_archive(self, borrowing_id: int) -> dict:
        return self._request("POST", f"/archive/borrowings/{borrowing_id}/return")

    def copy_archive(self, record_id: int, payload: dict) -> dict:
        return self._request("POST", f"/archive/records/{record_id}/copy", json=payload)

    def seal_archive(self, record_id: int, payload: dict) -> dict:
        return self._request("POST", f"/archive/records/{record_id}/seal", json=payload)

    def unseal_archive(self, record_id: int, payload: dict) -> dict:
        return self._request("POST", f"/archive/records/{record_id}/unseal", json=payload)

    def destroy_archive(self, record_id: int, payload: dict) -> dict:
        return self._request("POST", f"/archive/records/{record_id}/destroy", json=payload)

    def request_archive_destruction(self, record_id: int, payload: dict) -> dict:
        return self._request(
            "POST",
            f"/archive/records/{record_id}/destruction-requests",
            json=payload,
        )

    def list_archive_destruction_requests(self, status: str | None = None) -> list:
        params = {"status": status} if status else None
        return self._request("GET", "/archive/destruction-requests", params=params)

    def approve_archive_destruction(self, request_id: int, note: str = "") -> dict:
        return self._request(
            "POST",
            f"/archive/destruction-requests/{request_id}/approve",
            json={"note": note},
        )

    def reject_archive_destruction(self, request_id: int, note: str = "") -> dict:
        return self._request(
            "POST",
            f"/archive/destruction-requests/{request_id}/reject",
            json={"note": note},
        )

    def execute_archive_destruction(
        self, request_id: int, witness: str, note: str = ""
    ) -> dict:
        return self._request(
            "POST",
            f"/archive/destruction-requests/{request_id}/execute",
            json={"witness": witness, "note": note},
        )

    def upload_archive_destruction_attachment(
        self, request_id: int, file_path: str
    ) -> dict:
        with open(file_path, "rb") as handle:
            return self._request(
                "POST",
                f"/archive/destruction-requests/{request_id}/attachment",
                files={"file": (file_path.split("\\")[-1].split("/")[-1], handle)},
            )

    def archive_destruction_print_url(self, request_id: int) -> str:
        return f"{self.base_url}/archive/destruction-requests/{request_id}/print"

    # ---- 护士输液/医嘱执行 ----
    def sync_nursing(self, encounter_id: int) -> list:
        return self._request("POST", f"/nursing/encounters/{encounter_id}/sync")

    def list_nursing_orders(
        self, status: str | None = None, encounter_id: int | None = None
    ) -> list:
        params = {}
        if status:
            params["status"] = status
        if encounter_id:
            params["encounter_id"] = encounter_id
        return self._request("GET", "/nursing/orders", params=params)

    def prepare_nursing(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/nursing/orders/{order_id}/prepare", json=payload)

    def start_nursing(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/nursing/orders/{order_id}/start", json=payload)

    def observe_nursing(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/nursing/orders/{order_id}/observe", json=payload)

    def complete_nursing(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/nursing/orders/{order_id}/complete", json=payload)

    def skip_nursing(self, order_id: int, reason: str) -> dict:
        return self._request(
            "POST", f"/nursing/orders/{order_id}/skip", json={"reason": reason}
        )

    def list_imaging_items(self) -> list:
        return self._request("GET", "/pacs/items/")

    def create_imaging_request(self, encounter_id: int, item_id: int) -> dict:
        return self._request(
            "POST",
            f"/pacs/encounters/{encounter_id}/imaging-requests",
            json={"item_id": item_id},
        )

    def list_imaging_requests(self, encounter_id: int) -> list:
        return self._request("GET", f"/pacs/encounters/{encounter_id}/imaging-requests")

    # ---- 治疗 ----
    def create_treatment(
        self, encounter_id: int, item_id: int, quantity: int = 1, note: str = ""
    ) -> dict:
        return self._request(
            "POST",
            f"/treatments/encounters/{encounter_id}",
            json={"item_id": item_id, "quantity": quantity, "note": note},
        )

    def list_pending_treatments(self) -> list:
        return self._request("GET", "/treatments/", params={"status": "pending"})

    def list_treatments(self, encounter_id: int) -> list:
        return self._request("GET", f"/treatments/encounters/{encounter_id}")

    def execute_treatment(self, order_id: int) -> dict:
        return self._request("POST", f"/treatments/{order_id}/execute")

    # ---- 药房 ----
    def list_stocks(self, drug_id: int | None = None) -> list:
        params = {"drug_id": drug_id} if drug_id else {}
        return self._request("GET", "/pharmacy/stocks", params=params)

    def list_suppliers(self) -> list:
        return self._request("GET", "/suppliers/")

    def list_material_items(self, category: str | None = None) -> list:
        params = {"category": category} if category else {}
        return self._request("GET", "/materials/items/", params=params)

    # ---- 入库单（收货/验收/入库）----
    def create_inbound_order(self, payload: dict) -> dict:
        return self._request("POST", "/inbound/orders", json=payload)

    def list_inbound_orders(
        self, status: str | None = None, order_type: str | None = None
    ) -> list:
        params = {}
        if status:
            params["status"] = status
        if order_type:
            params["order_type"] = order_type
        return self._request("GET", "/inbound/orders", params=params)

    def get_inbound_order(self, order_id: int) -> dict:
        return self._request("GET", f"/inbound/orders/{order_id}")

    def check_inbound_order(self, order_id: int, items: list) -> dict:
        return self._request(
            "POST", f"/inbound/orders/{order_id}/check", json={"items": items}
        )

    def stock_inbound_order(self, order_id: int) -> dict:
        return self._request("POST", f"/inbound/orders/{order_id}/stock")

    def cancel_inbound_order(self, order_id: int) -> dict:
        return self._request("POST", f"/inbound/orders/{order_id}/cancel")

    # ---- 库房 / 出库单 ----
    def list_warehouse_stocks(self, drug_id: int | None = None) -> list:
        params = {"drug_id": drug_id} if drug_id else {}
        return self._request("GET", "/warehouse/stocks", params=params)

    def create_outbound_order(self, payload: dict) -> dict:
        return self._request("POST", "/warehouse/outbound-orders", json=payload)

    def list_outbound_orders(
        self, status: str | None = None, target_type: str | None = None
    ) -> list:
        params = {}
        if status:
            params["status"] = status
        if target_type:
            params["target_type"] = target_type
        return self._request("GET", "/warehouse/outbound-orders", params=params)

    def get_outbound_order(self, order_id: int) -> dict:
        return self._request("GET", f"/warehouse/outbound-orders/{order_id}")

    def approve_outbound_order(self, order_id: int) -> dict:
        return self._request("POST", f"/warehouse/outbound-orders/{order_id}/approve")

    def issue_outbound_order(self, order_id: int, items: list | None = None) -> dict:
        if items:
            return self._request(
                "POST", f"/warehouse/outbound-orders/{order_id}/issue", json={"items": items}
            )
        return self._request("POST", f"/warehouse/outbound-orders/{order_id}/issue")

    def cancel_outbound_order(self, order_id: int) -> dict:
        return self._request("POST", f"/warehouse/outbound-orders/{order_id}/cancel")

    def create_purchase_request_from_outbound(self, order_id: int) -> dict:
        return self._request(
            "POST", f"/warehouse/outbound-orders/{order_id}/purchase-request"
        )

    def list_purchase_requests(self, status: str | None = None) -> list:
        params = {"status": status} if status else None
        return self._request("GET", "/warehouse/purchase-requests", params=params)

    def approve_purchase_request(self, request_id: int) -> dict:
        return self._request(
            "POST", f"/warehouse/purchase-requests/{request_id}/approve"
        )

    def reject_purchase_request(self, request_id: int, reason: str) -> dict:
        return self._request(
            "POST",
            f"/warehouse/purchase-requests/{request_id}/reject",
            json={"reason": reason},
        )

    def order_purchase_request(self, request_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/warehouse/purchase-requests/{request_id}/order", json=payload
        )

    def receive_purchase_request(self, request_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/warehouse/purchase-requests/{request_id}/receive", json=payload
        )

    # ---- 中药 / 煎药 ----
    def list_tcm_herbs(self) -> list:
        return self._request("GET", "/tcm/herbs")

    def create_tcm_prescription(self, encounter_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/tcm/encounters/{encounter_id}/prescriptions", json=payload
        )

    def list_tcm_prescriptions(
        self, status: str | None = None, encounter_id: int | None = None
    ) -> list:
        params = {}
        if status:
            params["status"] = status
        if encounter_id:
            params["encounter_id"] = encounter_id
        return self._request("GET", "/tcm/prescriptions", params=params)

    def review_tcm(self, prescription_id: int) -> dict:
        return self._request("POST", f"/tcm/prescriptions/{prescription_id}/review")

    def dispense_tcm(self, prescription_id: int) -> dict:
        return self._request("POST", f"/tcm/prescriptions/{prescription_id}/dispense")

    def list_decoctions(self, status: str | None = None) -> list:
        params = {"status": status} if status else None
        return self._request("GET", "/tcm/decoction-orders", params=params)

    def soak_decoction(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/tcm/decoction-orders/{order_id}/soak", json=payload)

    def decoct_decoction(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/tcm/decoction-orders/{order_id}/decoct", json=payload)

    def package_decoction(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/tcm/decoction-orders/{order_id}/package", json=payload)

    def issue_decoction(self, order_id: int, payload: dict) -> dict:
        return self._request("POST", f"/tcm/decoction-orders/{order_id}/issue", json=payload)

    # ---- 手术室 ----
    def list_surgery_rooms(self) -> list:
        return self._request("GET", "/surgery/rooms")

    def create_surgery_room(self, payload: dict) -> dict:
        return self._request("POST", "/surgery/rooms", json=payload)

    def list_surgery_cases(self, status: str | None = None) -> list:
        params = {"status": status} if status else None
        return self._request("GET", "/surgery/cases", params=params)

    def create_surgery_case(self, payload: dict) -> dict:
        return self._request("POST", "/surgery/cases", json=payload)

    def surgery_case_detail(self, case_id: int) -> dict:
        return self._request("GET", f"/surgery/cases/{case_id}")

    def surgery_safety(self, case_id: int, phase: str, checklist: str = "") -> dict:
        return self._request(
            "POST",
            f"/surgery/cases/{case_id}/safety",
            json={"phase": phase, "checklist": checklist},
        )

    def surgery_preop(self, case_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/surgery/cases/{case_id}/preop", json=payload
        )

    def surgery_anesthesia(self, case_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/surgery/cases/{case_id}/anesthesia", json=payload
        )

    def start_surgery(self, case_id: int) -> dict:
        return self._request("POST", f"/surgery/cases/{case_id}/start")

    def surgery_record(self, case_id: int, payload: dict) -> dict:
        return self._request("POST", f"/surgery/cases/{case_id}/record", json=payload)

    def surgery_count(self, case_id: int, payload: dict) -> dict:
        return self._request("POST", f"/surgery/cases/{case_id}/counts", json=payload)

    def complete_surgery(self, case_id: int) -> dict:
        return self._request("POST", f"/surgery/cases/{case_id}/complete")

    def surgery_recovery(self, case_id: int, payload: dict) -> dict:
        return self._request("POST", f"/surgery/cases/{case_id}/recovery", json=payload)

    def attach_surgery_package(self, case_id: int, package_id: int) -> dict:
        return self._request(
            "POST", f"/surgery/cases/{case_id}/packages/{package_id}"
        )

    def surgery_material(self, case_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/surgery/cases/{case_id}/materials", json=payload
        )

    # ---- 治疗室 ----
    def list_treatment_rooms(self) -> list:
        return self._request("GET", "/treatment-room/rooms")

    def treatment_room_templates(self) -> list:
        return self._request("GET", "/treatment-room/templates")

    def treatment_room_workbench(self, day: str | None = None) -> dict:
        params = {"day": day} if day else None
        return self._request("GET", "/treatment-room/workbench", params=params)

    def create_treatment_room(self, payload: dict) -> dict:
        return self._request("POST", "/treatment-room/rooms", json=payload)

    def list_treatment_room_cases(self, status: str | None = None) -> list:
        params = {"status": status} if status else None
        return self._request("GET", "/treatment-room/cases", params=params)

    def create_treatment_room_case(self, payload: dict) -> dict:
        return self._request("POST", "/treatment-room/cases", json=payload)

    def start_treatment_room_case(self, case_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/treatment-room/cases/{case_id}/start", json=payload
        )

    def upload_treatment_consent(self, case_id: int, file_path: str) -> dict:
        with open(file_path, "rb") as handle:
            return self._request(
                "POST",
                f"/treatment-room/cases/{case_id}/consent-signature",
                files={"file": (file_path.split("\\")[-1].split("/")[-1], handle)},
            )

    def complete_treatment_room_case(self, case_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/treatment-room/cases/{case_id}/complete", json=payload
        )

    def cancel_treatment_room_case(self, case_id: int) -> dict:
        return self._request("POST", f"/treatment-room/cases/{case_id}/cancel")

    def treatment_room_material(self, case_id: int, payload: dict) -> dict:
        return self._request(
            "POST", f"/treatment-room/cases/{case_id}/materials", json=payload
        )

    def list_treatment_followups(self, status: str | None = "pending") -> list:
        params = {"status": status} if status else None
        return self._request("GET", "/treatment-room/follow-ups", params=params)

    # ---- 收费交班 / 日结 ----
    def cashier_daily(self, day: str | None = None) -> dict:
        params = {"day": day} if day else None
        return self._request("GET", "/cashier/daily", params=params)

    def open_cashier_shift(self, opening_float: float, note: str = "") -> dict:
        return self._request(
            "POST",
            "/cashier/shifts/open",
            json={"opening_float": opening_float, "note": note},
        )

    def close_cashier_shift(self, shift_id: int, counted_cash: float, note: str = "") -> dict:
        return self._request(
            "POST",
            f"/cashier/shifts/{shift_id}/close",
            json={"counted_cash": counted_cash, "note": note},
        )

    def print_invoice(self, payment_id: int) -> dict:
        return self._request("POST", f"/invoices/payments/{payment_id}/print")

    def void_invoice(self, payment_id: int, reason: str) -> dict:
        return self._request(
            "POST",
            f"/invoices/payments/{payment_id}/void",
            json={"reason": reason},
        )

    def complete_treatment_followup(self, followup_id: int, payload: dict | None = None) -> dict:
        return self._request(
            "POST",
            f"/treatment-room/follow-ups/{followup_id}/complete",
            json=payload or {},
        )

    def upload_followup_photo(self, followup_id: int, file_path: str) -> dict:
        with open(file_path, "rb") as handle:
            return self._request(
                "POST",
                f"/treatment-room/follow-ups/{followup_id}/photo",
                files={"file": (file_path.split("\\")[-1].split("/")[-1], handle)},
            )

    def cancel_treatment_followup(self, followup_id: int) -> dict:
        return self._request(
            "POST", f"/treatment-room/follow-ups/{followup_id}/cancel"
        )

    def list_material_stocks(self, item_id: int | None = None) -> list:
        params = {"item_id": item_id} if item_id else {}
        return self._request("GET", "/materials/stocks", params=params)

    def list_expiry_alerts(self, days: int = 90) -> dict:
        return self._request("GET", "/warehouse/expiry-alerts", params={"days": days})

    # ---- 追溯码 ----
    def trace_scan(self, mode: str, payload: dict) -> dict:
        return self._request("POST", f"/trace/scan/{mode}", json=payload)

    def trace_codes(
        self,
        trace_code: str | None = None,
        drug_id: int | None = None,
        batch_no: str | None = None,
        status: str | None = None,
        warehouse: str | None = None,
    ) -> list:
        params = {}
        for key, value in (
            ("trace_code", trace_code),
            ("drug_id", drug_id),
            ("batch_no", batch_no),
            ("status", status),
            ("warehouse", warehouse),
        ):
            if value:
                params[key] = value
        return self._request("GET", "/trace/codes", params=params)

    def ensure_drug_from_catalog(self, national_code: str) -> dict:
        return self._request(
            "POST", f"/insurance/catalog/{national_code}/ensure-drug"
        )

    def search_insurance_materials(
        self, q: str | None = None, category: str | None = None, limit: int = 500
    ) -> list:
        params: dict = {"limit": limit}
        if q:
            params["q"] = q
        if category:
            params["category"] = category
        return self._request("GET", "/insurance/materials/search", params=params)

    def ensure_material_from_catalog(self, code: str) -> dict:
        return self._request(
            "POST", f"/insurance/materials/{code}/ensure-item"
        )

    def trace_summary(self, drug_id: int | None = None, batch_no: str | None = None) -> dict:
        params = {}
        if drug_id:
            params["drug_id"] = drug_id
        if batch_no:
            params["batch_no"] = batch_no
        return self._request("GET", "/trace/codes/summary", params=params)

    # ---- 医保目录 ----
    def search_insurance_catalog(
        self, q: str | None = None, category: str | None = None, limit: int = 50
    ) -> list:
        params: dict = {"limit": limit}
        if q:
            params["q"] = q
        if category:
            params["category"] = category
        return self._request("GET", "/insurance/catalog/search", params=params)

    def stock_in(self, payload: dict) -> dict:
        return self._request("POST", "/pharmacy/stock-in", json=payload)

    def dispense(
        self,
        encounter_id: int,
        note: str = "",
        pickup_code: str = "",
        receiver_name: str = "",
        receiver_relation: str = "本人",
    ) -> dict:
        return self._request(
            "POST",
            "/pharmacy/dispense",
            json={
                "encounter_id": encounter_id,
                "note": note,
                "pickup_code": pickup_code,
                "receiver_name": receiver_name,
                "receiver_relation": receiver_relation,
            },
        )

    def pharmacy_worklist(self) -> list:
        return self._request("GET", "/pharmacy/worklist")

    def call_pharmacy(self, encounter_id: int, window_no: str, note: str = "") -> dict:
        return self._request(
            "POST",
            f"/pharmacy/calls/{encounter_id}",
            json={"window_no": window_no, "note": note},
        )

    def verify_pickup_code(self, code: str) -> dict:
        return self._request("GET", f"/pharmacy/pickup-codes/{code}")

    def retail_catalog(self) -> dict:
        return self._request("GET", "/pharmacy/retail-catalog")

    def create_retail_sale(self, payload: dict) -> dict:
        return self._request("POST", "/pharmacy/retail-sales", json=payload)

    def list_retail_sales(self) -> list:
        return self._request("GET", "/pharmacy/retail-sales")

    def refund_retail_sale(self, sale_id: int) -> dict:
        return self._request("POST", f"/pharmacy/retail-sales/{sale_id}/refund")

    def retail_print_url(self, sale_id: int) -> str:
        return f"{self.base_url}/print/retail/{sale_id}"

    def upload_dispense_signature(self, dispense_id: int, file_path: str) -> dict:
        with open(file_path, "rb") as handle:
            return self._request(
                "POST",
                f"/pharmacy/dispense/{dispense_id}/signature",
                files={"file": (file_path.split("\\")[-1].split("/")[-1], handle)},
            )

    def return_dispense(self, dispense_id: int) -> dict:
        return self._request("POST", f"/pharmacy/dispense/{dispense_id}/return")

    # ---- 分诊 ----
    def create_triage_ticket(
        self, registration_id: int, payload: dict | None = None
    ) -> dict:
        body = {"registration_id": registration_id}
        body.update(payload or {})
        return self._request("POST", "/triage/tickets", json=body)

    def triage_queue(self) -> list:
        return self._request("GET", "/triage/queue")

    def call_ticket(self, ticket_id: int) -> dict:
        return self._request("POST", f"/triage/tickets/{ticket_id}/call")

    def pass_ticket(self, ticket_id: int) -> dict:
        return self._request("POST", f"/triage/tickets/{ticket_id}/pass")

    # ---- 费用 / 收费 / 退费 ----
    def get_charges(self, encounter_id: int) -> list:
        return self._request("GET", f"/charges/encounters/{encounter_id}")

    def resolve_prescription_barcode(self, code: str) -> dict:
        return self._request("GET", f"/encounters/by-barcode/{quote(code.strip())}")

    def get_charge_summary(self, encounter_id: int) -> dict:
        return self._request("GET", f"/charges/encounters/{encounter_id}/summary")

    def create_payment(
        self,
        encounter_id: int,
        channel: str = "cash",
        auth_code: str = "",
        card_no: str = "",
    ) -> dict:
        payload = {"encounter_id": encounter_id, "channel": channel}
        if auth_code:
            payload["auth_code"] = auth_code
        if card_no:
            payload["card_no"] = card_no
        return self._request("POST", "/payments/", json=payload)

    def refund_payment(
        self, payment_id: int, items: list | None = None, reason: str = ""
    ) -> dict:
        payload: dict = {}
        if items:
            payload["items"] = items
        if reason:
            payload["reason"] = reason
        if payload:
            return self._request(
                "POST", f"/payments/{payment_id}/refund", json=payload
            )
        return self._request("POST", f"/payments/{payment_id}/refund")

    def get_payment(self, payment_id: int) -> dict:
        return self._request("GET", f"/payments/{payment_id}")

    # ---- 打印页 URL ----
    def prescription_print_url(self, encounter_id: int) -> str:
        return f"{self.base_url}/print/prescription/{encounter_id}"

    def receipt_print_url(self, payment_id: int) -> str:
        return f"{self.base_url}/print/receipt/{payment_id}"
