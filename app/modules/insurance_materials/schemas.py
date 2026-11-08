from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InsuranceMaterialResponse(BaseModel):
    id: int
    code: str
    name: str
    category: str
    spec: str
    model: str
    manufacturer: str
    unit: str
    material_type: str
    registration_no: str
    note: str
    model_config = ConfigDict(from_attributes=True)


class MaterialImportResult(BaseModel):
    total: int
    inserted: int
    updated: int


class MaterialSyncRequest(BaseModel):
    url: str
