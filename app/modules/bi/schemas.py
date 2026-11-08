from datetime import date

from pydantic import BaseModel


class OverviewResponse(BaseModel):
    patients_total: int
    registrations_total: int
    encounters_total: int
    admissions_active: int
    dispenses_total: int
    today_paid_count: int
    today_paid_amount: float
    today_refunded_count: int
    today_refunded_amount: float
    today_insurance_amount: float
    today_lab_requests: int
    today_imaging_requests: int
    today_admissions_in: int
    today_discharges: int


class RevenueTrendItem(BaseModel):
    date: str
    paid_count: int
    paid_amount: float


class TopDiagnosisItem(BaseModel):
    diagnosis: str
    count: int


class TopDrugItem(BaseModel):
    drug_id: int
    drug_name: str
    quantity: int
