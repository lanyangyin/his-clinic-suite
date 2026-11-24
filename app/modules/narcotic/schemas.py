from pydantic import BaseModel, Field


class AmpouleReturnRequest(BaseModel):
    drug_id: int
    prescription_id: int | None = None
    patient_id: int | None = None
    batch_no: str = ""
    quantity: int = Field(gt=0)
    witness: str = Field(min_length=1, max_length=50)
    note: str = Field(default="", max_length=300)


class InventoryCheckCreate(BaseModel):
    drug_id: int
    batch_no: str = ""
    counted_qty: int = Field(ge=0)
    reason: str = Field(default="", max_length=300)


class InventoryCheckReview(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=300)
