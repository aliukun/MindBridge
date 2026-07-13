from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """创建并配置一个 FastAPI 应用实例"""

    settings = get_settings()

    application = FastAPI(
        title = settings.app_name,
        version = settings.app_version,
    )

    application.include_router(router)

    return application

app = create_app()