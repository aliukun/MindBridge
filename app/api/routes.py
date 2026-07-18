from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.models.entities import UserAccount
from app.schemas.chat import (
    ChatHistoryPublic,
    ChatMessageCreate,
    ChatMessagePublic,
    ChatSessionCreate,
    ChatSessionPublic,
)
from app.schemas.users import UserPublic
from app.services.chat_service import (
    ChatSessionNotFoundError,
    create_chat_session,
    get_chat_history,
)
from app.services.message_service import process_user_message

router = APIRouter()


@router.get("/actuator/health")
def health() -> dict[str, str]:
    """返回应用本身的基础运行状态。"""

    settings = get_settings()

    return {
        "status": "UP",
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get(
    "/api/users/me",
    response_model=UserPublic,
)
def read_current_user(
    current_user: Annotated[
        UserAccount,
        Depends(get_current_user),
    ],
) -> UserAccount:
    """返回当前用户的公开账户信息。"""

    return current_user


@router.get("/api/admin/ping")
def admin_ping(
    current_admin: Annotated[
        UserAccount,
        Depends(require_admin),
    ],
) -> dict[str, str]:
    """仅允许管理员访问的验证接口。"""

    return {
        "status": "ADMIN_OK",
        "username": current_admin.username,
    }


@router.post(
    "/api/chat/sessions",
    response_model=ChatSessionPublic,
    status_code=status.HTTP_201_CREATED,
)
def start_chat_session(
    request: ChatSessionCreate,
    current_user: Annotated[
        UserAccount,
        Depends(get_current_user),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
):
    """为当前用户创建一个聊天会话。"""

    try:
        chat_session = create_chat_session(
            database,
            owner=current_user,
            title=request.title,
        )

        database.commit()
    except Exception:
        database.rollback()
        raise

    database.refresh(chat_session)

    return chat_session


@router.post(
    "/api/chat/sessions/{session_public_id}/messages",
    response_model=ChatMessagePublic,
    status_code=status.HTTP_201_CREATED,
)
def save_user_message(
    session_public_id: UUID,
    request: ChatMessageCreate,
    current_user: Annotated[
        UserAccount,
        Depends(get_current_user),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
):
    """保存用户消息并执行后台风险硬规则。"""

    try:
        result = process_user_message(
            database,
            owner=current_user,
            session_public_id=session_public_id,
            content=request.content,
        )

        database.commit()
    except ChatSessionNotFoundError as error:
        database.rollback()

        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.CHAT_SESSION_NOT_FOUND,
            detail="Chat session not found.",
        ) from error
    except Exception:
        database.rollback()
        raise

    database.refresh(result.user_message)

    return result.user_message


@router.get(
    "/api/chat/sessions/{session_public_id}/messages",
    response_model=ChatHistoryPublic,
)
def read_chat_history(
    session_public_id: UUID,
    current_user: Annotated[
        UserAccount,
        Depends(get_current_user),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ChatHistoryPublic:
    """查询当前用户自己的聊天历史。"""

    try:
        history = get_chat_history(
            database,
            owner=current_user,
            session_public_id=session_public_id,
        )
    except ChatSessionNotFoundError as error:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.CHAT_SESSION_NOT_FOUND,
            detail="Chat session not found.",
        ) from error

    return ChatHistoryPublic(
        session=ChatSessionPublic.model_validate(history.session),
        messages=[
            ChatMessagePublic.model_validate(message) for message in history.messages
        ],
    )
