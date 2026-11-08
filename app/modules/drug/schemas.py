from pydantic import BaseModel, ConfigDict, Field


class DrugCreate(BaseModel):
    name: str
    spec: str = ""
    unit: str = ""
    base_price: float = Field(ge=0)
    insurance_ratio: float = Field(default=0.7, ge=0, le=1)
    # 抗菌药物分级：0 非抗菌药 / 1 非限制 / 2 限制 / 3 特殊使用
    antibiotic_level: int = Field(default=0, ge=0, le=3)
    # 医保贯标与生产信息
    insurance_code: str = ""
    approval_no: str = ""
    manufacturer: str = ""
    dosage_form: str = ""


class DrugResponse(DrugCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)
