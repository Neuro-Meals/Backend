from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]

    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=2,
        max_length=2000,
    )

    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=10,
    )


class ChatResponse(BaseModel):
    answer: str
    model: str
    scope: str = "nutriomeals"
    authenticated: bool = False