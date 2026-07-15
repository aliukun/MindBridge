from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, require_admin
from app.core.config import get_settings
from app.models.entities import UserAccount
from app.schemas.users import UserPublic

router = APIRouter()

@router.get("/actuator/health")
def health() -> dict[str, str]:
    """返回应用本身的基础运行状态"""

    settings = get_settings()

    return {
        "status": "UP",
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }

@router.get(
    "/api/users/me",
    response_model=UserPublic
)
def read_current_user(
        current_user: Annotated[
            UserAccount,
            Depends(get_current_user),
        ],
) -> UserAccount:
    """返回当前用户的公开账户信息"""

    return current_user

@router.get("/api/admin/ping")
def admin_ping(
        current_admin: Annotated[
            UserAccount,
            Depends(require_admin),
        ],
) -> dict[str, str]:
    """仅允许管理员访问的验证接口"""

    return {
        "status": "ADMIN_OK",
        "username": current_admin.username,
    }