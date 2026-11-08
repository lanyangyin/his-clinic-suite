from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    contact: str = Field(default="", max_length=50)
    phone: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=200)


class SupplierResponse(SupplierCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)
