from pydantic import BaseModel


class DoctorPerformanceItem(BaseModel):
    doctor_id: int
    doctor_name: str
    encounters: int
    prescriptions: int
    outpatient_revenue: float
    admissions: int
    orders: int
