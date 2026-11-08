from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DailyCloseRequest(BaseModel):
    close_date: date


class ClosureResponse(BaseModel):
    id: int
    close_date: date
    outpatient_paid_count: int
    outpatient_paid_amount: float
    outpatient_refunded_count: int
    outpatient_refunded_amount: float
    insurance_amount: float
    inpatient_charge_count: int
    inpatient_charge_amount: float
    closed_at: datetime
    closed_by: str
    model_config = ConfigDict(from_attributes=True)


class MonthlySummaryResponse(BaseModel):
    month: str
    outpatient_paid_count: int
    outpatient_paid_amount: float
    outpatient_refunded_count: int
    outpatient_refunded_amount: float
    insurance_amount: float
    inpatient_charge_count: int
    inpatient_charge_amount: float
    closed_days: int
