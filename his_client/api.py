"""REST API 封装：客户端所有服务端交互都走这里（便于测试与复用）。"""
from __future__ import annotations

import requests


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
    def list_patients(self, name: str | None = None, id_number: str | None = None) -> list:
        params = {}
        if name:
            params["name"] = name
        if id_number:
            params["id_number"] = id_number
        return self._request("GET", "/patients/", params=params)

    def create_patient(self, name: str, id_number: str, phone: str = "") -> dict:
        return self._request(
            "POST",
            "/patients/",
            json={"name": name, "id_number": id_number, "phone": phone or None},
        )

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

    def create_encounter(self, registration_id: int, diagnosis: str = "") -> dict:
        return self._request(
            "POST",
            "/encounters/",
            json={"registration_id": registration_id, "diagnosis": diagnosis},
        )

    # ---- 病历 ----
    def get_medical_record(self, encounter_id: int) -> dict:
        return self._request("GET", f"/encounters/{encounter_id}/medical-record")

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

    def dispense(self, encounter_id: int) -> dict:
        return self._request("POST", "/pharmacy/dispense", json={"encounter_id": encounter_id})

    def return_dispense(self, dispense_id: int) -> dict:
        return self._request("POST", f"/pharmacy/dispense/{dispense_id}/return")

    # ---- 分诊 ----
    def create_triage_ticket(self, registration_id: int) -> dict:
        return self._request(
            "POST", "/triage/tickets", json={"registration_id": registration_id}
        )

    def triage_queue(self) -> list:
        return self._request("GET", "/triage/queue")

    def call_ticket(self, ticket_id: int) -> dict:
        return self._request("POST", f"/triage/tickets/{ticket_id}/call")

    def pass_ticket(self, ticket_id: int) -> dict:
        return self._request("POST", f"/triage/tickets/{ticket_id}/pass")

    # ---- 费用 / 收费 / 退费 ----
    def get_charges(self, encounter_id: int) -> list:
        return self._request("GET", f"/charges/encounters/{encounter_id}")

    def get_charge_summary(self, encounter_id: int) -> dict:
        return self._request("GET", f"/charges/encounters/{encounter_id}/summary")

    def create_payment(self, encounter_id: int) -> dict:
        return self._request("POST", "/payments/", json={"encounter_id": encounter_id})

    def refund_payment(self, payment_id: int) -> dict:
        return self._request("POST", f"/payments/{payment_id}/refund")

    def get_payment(self, payment_id: int) -> dict:
        return self._request("GET", f"/payments/{payment_id}")

    # ---- 打印页 URL ----
    def prescription_print_url(self, encounter_id: int) -> str:
        return f"{self.base_url}/print/prescription/{encounter_id}"

    def receipt_print_url(self, payment_id: int) -> str:
        return f"{self.base_url}/print/receipt/{payment_id}"
