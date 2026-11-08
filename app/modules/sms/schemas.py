from pydantic import BaseModel, ConfigDict, Field


class SmsSend(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    content: str = Field(min_length=1, max_length=200)
    template: str = Field(default="custom", max_length=30)


class SmsResponse(BaseModel):
    id: int
    phone: str
    content: str
    template: str
    status: str
    model_config = ConfigDict(from_attributes=True)
