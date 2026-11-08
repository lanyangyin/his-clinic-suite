from pydantic import BaseModel


class DepartmentRevenueItem(BaseModel):
    department_id: int
    department_name: str
    encounter_count: int
    paid_amount: float
    refunded_amount: float
    registration_amount: float
    consultation_amount: float
    drug_amount: float
    lab_amount: float
    imaging_amount: float
    treatment_amount: float
    other_amount: float
