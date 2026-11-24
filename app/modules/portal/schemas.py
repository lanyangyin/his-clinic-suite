from datetime import date, datetime

from pydantic import BaseModel, Field


class PortalRegistrationItem(BaseModel):
    id: int
    doctor_id: int
    status: str


class PortalEncounterItem(BaseModel):
    id: int
    diagnosis: str
    status: str


class PortalPatientResponse(BaseModel):
    id: int
    name: str
    id_number: str
    phone: str | None
    registrations: list[PortalRegistrationItem]
    encounters: list[PortalEncounterItem]


class PortalLabItem(BaseModel):
    id: int
    item_name: str
    result: str | None
    reported_at: datetime | None


class PortalImagingItem(BaseModel):
    id: int
    item_name: str
    report: str | None
    image_url: str
    reported_at: datetime | None


class PortalReportsResponse(BaseModel):
    patient_id: int
    labs: list[PortalLabItem]
    imaging: list[PortalImagingItem]


class PortalAccessRequest(BaseModel):
    id_number: str = Field(min_length=1, max_length=30)
    phone: str = Field(min_length=1, max_length=20)
    code: str = Field(default="", max_length=10)


class PortalCodeRequest(BaseModel):
    id_number: str = Field(min_length=1, max_length=30)
    phone: str = Field(min_length=1, max_length=20)


class PortalAccessResponse(BaseModel):
    token: str
    expires_in: int
