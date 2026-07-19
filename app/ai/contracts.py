from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

MAX_AI_MESSAGE_LENGTH = 10_000
MAX_AI_MESSAGES = 64
MAX_AI_TOKENS = 4096
MAX_AI_COMPLETION_LENGTH = 50_000
MAX_AI_STREAM_DELTA_LENGTH = 10_000


class AiRole(StrEnum):
    """允许发送给 AI Provider 的消息角色。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AiFinishReason(StrEnum):
    """一次 AI 生成停止的稳定原因。"""

    STOP = "stop"
    LENGTH = "length"


class ProviderState(StrEnum):
    """Provider 的通用可用状态。"""

    READY = "READY"
    UNAVAILABLE = "UNAVAILABLE"
    MISCONFIGURED = "MISCONFIGURED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"


class AiMessage(BaseModel):
    """发送给 AI Provider 的单条内部消息。"""

    role: AiRole
    content: str = Field(
        min_length=1,
        max_length=MAX_AI_MESSAGE_LENGTH,
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    @field_validator("content")
    @classmethod
    def reject_blank_content(
        cls,
        value: str,
    ) -> str:
        if not value.strip():
            raise ValueError("AI message content must not be blank.")

        return value


class AiRequestOptions(BaseModel):
    """一次 AI 请求所使用的供应商无关选项。"""

    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        allow_inf_nan=False,
        strict=True,
    )
    max_tokens: int = Field(
        default=512,
        ge=1,
        le=MAX_AI_TOKENS,
        strict=True,
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class AiRequest(BaseModel):
    """一次完整 AI 请求，而不是一条孤立消息。"""

    messages: tuple[AiMessage, ...] = Field(
        min_length=1,
        max_length=MAX_AI_MESSAGES,
    )
    options: AiRequestOptions = Field(
        default_factory=AiRequestOptions,
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class AiCompletion(BaseModel):
    """一次非流式 AI 调用的完整结果。"""

    text: str = Field(
        min_length=1,
        max_length=MAX_AI_COMPLETION_LENGTH,
    )
    provider: str = Field(
        min_length=1,
        max_length=64,
    )
    model: str = Field(
        min_length=1,
        max_length=256,
    )
    finish_reason: AiFinishReason

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    @field_validator("text")
    @classmethod
    def reject_blank_text(
        cls,
        value: str,
    ) -> str:
        if not value.strip():
            raise ValueError("AI completion text must not be blank.")

        return value


class AiStreamChunk(BaseModel):
    """一次流式调用产生的增量数据或终止块。"""

    index: int = Field(
        ge=0,
        strict=True,
    )
    delta: str = Field(
        default="",
        max_length=MAX_AI_STREAM_DELTA_LENGTH,
    )
    done: bool = False
    finish_reason: AiFinishReason | None = None

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    @model_validator(mode="after")
    def validate_chunk_state(self) -> Self:
        if self.done and self.finish_reason is None:
            raise ValueError("A completed chunk requires a finish reason.")

        if not self.done and self.finish_reason is not None:
            raise ValueError("A non-terminal chunk cannot have a finish reason.")

        if not self.done and not self.delta:
            raise ValueError("A non-terminal chunk must contain a delta.")

        return self


class ProviderStatus(BaseModel):
    """Provider 的供应商无关状态。"""

    provider: str = Field(
        min_length=1,
        max_length=64,
    )
    state: ProviderState
    model: str = Field(
        min_length=1,
        max_length=256,
    )
    detail: str | None = Field(
        default=None,
        max_length=500,
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )
