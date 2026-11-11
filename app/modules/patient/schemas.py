from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Gender = Literal["male", "female", "unknown"]
IdType = Literal["id_card", "passport", "hk_macau_taiwan", "other", "none"]
InsuranceType = Literal[
    "employee", "resident", "remote", "self_pay", "commercial", "other"
]
AllergyStatus = Literal["none", "unknown", "present"]


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    id_type: IdType = "id_card"
    id_number: str | None = Field(default=None, max_length=30)
    gender: Gender = "unknown"
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str = Field(default="", max_length=200)
    emergency_contact_name: str = Field(default="", max_length=50)
    emergency_contact_relation: str = Field(default="", max_length=20)
    emergency_contact_phone: str = Field(default="", max_length=20)
    insurance_type: InsuranceType = "self_pay"
    allergy_status: AllergyStatus = "unknown"
    allergy_detail: str = Field(default="", max_length=200)
    special_history: str = Field(default="", max_length=500)
    privacy_consent: bool = False

    @model_validator(mode="after")
    def _check_identity(self):
        self.id_number = (self.id_number or "").strip() or None
        if self.id_type == "none":
            self.id_number = None
        elif not self.id_number:
            raise ValueError("该证件类型必须填写证件号码")
        if self.phone:
            self.phone = self.phone.strip() or None
        if self.allergy_status != "present":
            self.allergy_detail = ""
        return self


class PatientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    id_type: IdType | None = None
    id_number: str | None = Field(default=None, max_length=30)
    gender: Gender | None = None
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=200)
    emergency_contact_name: str | None = Field(default=None, max_length=50)
    emergency_contact_relation: str | None = Field(default=None, max_length=20)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    insurance_type: InsuranceType | None = None
    allergy_status: AllergyStatus | None = None
    allergy_detail: str | None = Field(default=None, max_length=200)
    special_history: str | None = Field(default=None, max_length=500)
    privacy_consent: bool | None = None


class PatientResponse(BaseModel):
    id: int
    patient_no: str | None
    name: str
    id_type: str
    id_number: str | None
    gender: str
    birth_date: date | None
    age: int | None
    phone: str | None
    address: str
    emergency_contact_name: str
    emergency_contact_relation: str
    emergency_contact_phone: str
    insurance_type: str
    allergy_status: str
    allergy_detail: str
    allergy_label: str
    special_history: str
    privacy_consent_at: datetime | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DuplicateCandidate(BaseModel):
    id: int
    patient_no: str | None
    name: str
    gender: str
    birth_date: date | None
    phone: str | None
    id_number: str | None
    exact: bool


class DuplicateCheckResponse(BaseModel):
    exact: bool
    candidates: list[DuplicateCandidate]


class PatientCardCreate(BaseModel):
    card_uid: str = Field(min_length=4, max_length=64)
    note: str = Field(default="", max_length=200)


class PatientCardResponse(BaseModel):
    id: int
    patient_id: int
    patient_no: str | None = None
    patient_name: str = ""
    card_uid: str
    status: str
    issued_at: datetime
    issued_by: str
    note: str



class ClinicalProfileUpdate(BaseModel):
    allergy_status: AllergyStatus | None = None
    allergy_detail: str | None = Field(default=None, max_length=200)
    special_history: str | None = Field(default=None, max_length=500)
    reason: str = Field(min_length=1, max_length=300)


class ClinicalChangeResponse(BaseModel):
    id: int
    patient_id: int
    field: str
    old_value: str
    new_value: str
    reason: str
    changed_by: str
    changed_at: datetime
    model_config = ConfigDict(from_attributes=True)
