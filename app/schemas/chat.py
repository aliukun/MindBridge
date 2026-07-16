from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ChatSessionCreate(BaseModel):
    """客户端创建会话时允许提交的数据。"""

    title: str = Field(
        min_length=1,
        max_length=160,
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @field_validator("title")
    @classmethod
    def normalize_title(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Title must not be blank."
            )

        return normalized


class ChatMessageCreate(BaseModel):
    """客户端发送一条用户消息时允许提交的数据。"""

    content: str = Field(
        min_length=1,
        max_length=10_000,
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @field_validator("content")
    @classmethod
    def normalize_content(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Message content must not be blank."
            )

        return normalized


class ChatSessionPublic(BaseModel):
    """允许返回给客户端的会话信息。"""

    public_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ChatMessagePublic(BaseModel):
    """允许返回给会话所有者的消息。"""

    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ChatHistoryPublic(BaseModel):
    """会话信息及其历史消息。"""

    session: ChatSessionPublic
    messages: list[ChatMessagePublic]