from pydantic import BaseModel, ConfigDict, Field


class DictEntryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)


class DictEntryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)
    active: bool | None = None


class DictEntryResponse(DictEntryCreate):
    id: int
    dict_type: str
    active: bool
    model_config = ConfigDict(from_attributes=True)


class DictTypeItem(BaseModel):
    dict_type: str
    entry_count: int
