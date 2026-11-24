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
    controlled_level: str = Field(default="", pattern="^(|narcotic|psychotropic1)$")


class DrugUpdate(BaseModel):
    name: str | None = None
    spec: str | None = None
    unit: str | None = None
    base_price: float | None = Field(default=None, ge=0)
    insurance_ratio: float | None = Field(default=None, ge=0, le=1)
    antibiotic_level: int | None = Field(default=None, ge=0, le=3)
    high_alert: bool | None = None
    is_otc: bool | None = None
    ingredient: str | None = None
    barcode: str | None = None
    insurance_code: str | None = None
    approval_no: str | None = None
    manufacturer: str | None = None
    dosage_form: str | None = None
    controlled_level: str | None = Field(default=None, pattern="^(|narcotic|psychotropic1)$")


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
