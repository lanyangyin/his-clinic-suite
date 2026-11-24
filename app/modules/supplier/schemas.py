from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    contact: str = Field(default="", max_length=50)
    phone: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=200)
    license_no: str = Field(default="", max_length=60)
    license_expiry: date | None = None
    first_business_approved: bool = False


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    contact: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=200)
    license_no: str | None = Field(default=None, max_length=60)
    license_expiry: date | None = None
    status: str | None = Field(default=None, pattern="^(active|suspended|blacklist)$")
    first_business_approved: bool | None = None
    blacklist_reason: str | None = Field(default=None, max_length=200)


class SupplierResponse(SupplierCreate):
    id: int
    status: str = "active"
    blacklist_reason: str = ""
    model_config = ConfigDict(from_attributes=True)
