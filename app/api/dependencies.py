from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.ai.contracts import AiRequestOptions
from app.ai.providers.base import AiProvider
from app.core.config import Settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.entities import ROLE_ADMIN, UserAccount
from app.services.user_service import get_user_by_username

basic_auth = HTTPBasic(realm="MindBridge")

_dummy_password_hash = hash_password("dummy-password-never-used-for-login")


def _incorrect_credentials_exception() -> HTTPException:
    """构造统一的身份认证失败响应。"""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={
            "WWW-Authenticate": ('Basic realm="MindBridge"'),
        },
    )


def get_current_user(
    credentials: Annotated[
        HTTPBasicCredentials,
        Depends(basic_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> UserAccount:
    """验证 HTTP Basic 凭据并返回当前用户。"""

    user = get_user_by_username(
        database,
        credentials.username,
    )

    password_hash_to_check = (
        user.password_hash if user is not None else _dummy_password_hash
    )

    password_is_valid = verify_password(
        credentials.password,
        password_hash_to_check,
    )

    if user is None or not password_is_valid:
        raise _incorrect_credentials_exception()

    return user


def require_admin(
    current_user: Annotated[
        UserAccount,
        Depends(get_current_user),
    ],
) -> UserAccount:
    """只允许管理员继续访问。"""

    if ROLE_ADMIN not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )

    return current_user


def get_ai_provider(
    request: Request,
) -> AiProvider:
    """从应用生命周期中取得当前 Provider。"""

    provider = getattr(
        request.app.state,
        "ai_provider",
        None,
    )

    if not isinstance(provider, AiProvider):
        raise RuntimeError("AI provider is not initialized.")

    return provider


def get_ai_request_options(
    request: Request,
) -> AiRequestOptions:
    """取得由集中配置构造的默认请求参数。"""

    options = getattr(
        request.app.state,
        "ai_request_options",
        None,
    )

    if not isinstance(options, AiRequestOptions):
        raise RuntimeError("AI request options are not initialized.")

    return options


def get_http_client(
    request: Request,
) -> httpx.AsyncClient:
    """取得由 lifespan 持有的共享异步 HTTP 客户端。"""

    http_client = getattr(
        request.app.state,
        "http_client",
        None,
    )

    if not isinstance(http_client, httpx.AsyncClient):
        raise RuntimeError("HTTP client is not initialized.")

    return http_client


def get_application_settings(
    request: Request,
) -> Settings:
    """取得创建当前应用时实际使用的配置。"""

    settings = getattr(
        request.app.state,
        "settings",
        None,
    )

    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings are not initialized.")

    return settings
