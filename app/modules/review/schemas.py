from pydantic import BaseModel


class ReviewSummary(BaseModel):
    prescription_count: int
    item_count: int
    avg_items: float
    total_amount: float
    avg_amount: float
    antibiotic_prescriptions: int
    antibiotic_rate: float
    injection_prescriptions: int
    injection_rate: float


class ReviewIssue(BaseModel):
    encounter_id: int
    patient_name: str
    doctor_name: str
    drug_name: str
    quantity: int
    unit_price: float
    amount: float
    reason: str


class ReviewItem(BaseModel):
    drug_name: str
    quantity: int
    unit_price: float
    amount: float
    dosage: str
    frequency: str
    route: str
    days: int
    antibiotic_level: int


class ReviewDetail(BaseModel):
    encounter_id: int
    patient_name: str
    doctor_name: str
    diagnosis: str
    items: list[ReviewItem]
    total_amount: float
