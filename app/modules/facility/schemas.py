from pydantic import BaseModel, ConfigDict, Field


class CampusCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    address: str = Field(default="", max_length=200)


class CampusResponse(CampusCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)


class RoomCreate(BaseModel):
    campus_id: int
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    department_id: int | None = None


class RoomResponse(RoomCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)
