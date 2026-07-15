from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class HealthResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: str


class ErrorResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)
    request_id: str
