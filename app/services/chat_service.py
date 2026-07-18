from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_ROLE_USER,
    ChatMessage,
    ChatSession,
    UserAccount,
)

MAX_TITLE_LENGTH = 160
MAX_MESSAGE_LENGTH = 10_000

ALLOWED_MESSAGE_ROLES = {
    MESSAGE_ROLE_USER,
    MESSAGE_ROLE_ASSISTANT,
}


class ChatSessionNotFoundError(LookupError):
    """会话不存在，或者不属于当前用户"""


@dataclass(frozen=True)
class ChatHistoryResult:
    """从数据库中查询到的会话和消息集合"""

    session: ChatSession
    messages: list[ChatMessage]


def _normalize_text(
    value: str,
    *,
    field_name: str,
    maximum_length: int,
) -> str:
    """清理并验证标题或消息文本"""

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")

    if len(normalized) > maximum_length:
        raise ValueError(f"{field_name} must not exceed {maximum_length} characters.")

    return normalized


def create_chat_session(
    database: Session,
    *,
    owner: UserAccount,
    title: str,
) -> ChatSession:
    """创建会话并 flush，但不负责 commit"""

    normalized_title = _normalize_text(
        title,
        field_name="Title",
        maximum_length=MAX_TITLE_LENGTH,
    )

    chat_session = ChatSession(
        user_id=owner.id,
        title=normalized_title,
    )

    database.add(chat_session)
    database.flush()

    return chat_session


def get_owned_chat_session(
    database: Session,
    *,
    owner: UserAccount,
    public_id: str | UUID,
) -> ChatSession:
    """同时按公开 ID 和用户 ID 查询会话"""

    statement = select(ChatSession).where(
        ChatSession.user_id == owner.id,
        ChatSession.public_id == str(public_id),
    )

    chat_session = database.scalars(statement).one_or_none()

    if chat_session is None:
        raise ChatSessionNotFoundError("Chat session not found.")

    return chat_session


def create_chat_message(
    database: Session,
    *,
    owner: UserAccount,
    session_public_id: str | UUID,
    role: str,
    content: str,
) -> ChatMessage:
    """保存一条用户或助手消息，但不负责 commit"""

    if role not in ALLOWED_MESSAGE_ROLES:
        raise ValueError(f"Unsupported message role: {role}.")

    normalized_content = _normalize_text(
        content,
        field_name="Message content",
        maximum_length=MAX_MESSAGE_LENGTH,
    )

    chat_session = get_owned_chat_session(
        database,
        owner=owner,
        public_id=session_public_id,
    )

    message = ChatMessage(
        session=chat_session,
        role=role,
        content=normalized_content,
    )

    chat_session.touch()

    database.add(message)
    database.flush()

    return message


def get_chat_history(
    database: Session,
    *,
    owner: UserAccount,
    session_public_id: str | UUID,
) -> ChatHistoryResult:
    """按稳定时间顺序查询当前用户的聊天历史"""

    chat_session = get_owned_chat_session(
        database,
        owner=owner,
        public_id=session_public_id,
    )

    statement = (
        select(ChatMessage)
        .where(
            ChatMessage.session_id == chat_session.id,
        )
        .order_by(
            ChatMessage.created_at.asc(),
            ChatMessage.id.asc(),
        )
    )

    messages = list(database.scalars(statement).all())

    return ChatHistoryResult(
        session=chat_session,
        messages=messages,
    )
