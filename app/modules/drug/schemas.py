from pydantic import BaseModel, ConfigDict, Field


class DrugCreate(BaseModel):
    name: str
    spec: str = ""
    unit: str = ""
    base_price: float = Field(ge=0)
    insurance_ratio: float = Field(default=0.7, ge=0, le=1)
    # 抗菌药物分级：0 非抗菌药 / 1 非限制 / 2 限制 / 3 特殊使用
    antibiotic_level: int = Field(default=0, ge=0, le=3)
    # 高危药品：配药需要第二人核对
    high_alert: bool = False
    # 非处方药：允许零售
    is_otc: bool = False
    # 主要成分/复方成分
    ingredient: str = ""
    # 药品条码
    barcode: str = ""
    # 医保贯标与生产信息
    insurance_code: str = ""
    approval_no: str = ""
    manufacturer: str = ""
    dosage_form: str = ""


class DrugResponse(DrugCreate):
    id: int
    insurance_category: str = ""
    insurance_match_status: str = "unmatched"
    model_config = ConfigDict(from_attributes=True)


class DrugInteractionCreate(BaseModel):
    drug_a_id: int
    drug_b_id: int
    severity: str = Field(default="block", pattern="^(block|warn)$")
    note: str = ""


class DrugInteractionResponse(DrugInteractionCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)
