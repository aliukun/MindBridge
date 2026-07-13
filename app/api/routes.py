from fastapi import APIRouter

from app.core.config import get_settings

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