from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.ai.factory import (
    build_ai_provider,
    build_ai_request_options,
)
from app.api.routes import router
from app.core.bootstrap import bootstrap_database
from app.core.config import get_settings
from app.core.errors import (
    RequestIdMiddleware,
    register_exception_handlers,
)
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """管理应用启动和关闭期间需要执行的操作"""

    bootstrap_database()

    yield


def create_app() -> FastAPI:
    """创建并配置一个 FastAPI 应用实例"""

    settings = get_settings()

    ai_provider = build_ai_provider(
        settings.ai_provider,
    )
    ai_request_options = build_ai_request_options(
        settings,
    )

    configure_logging(settings)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    application.state.ai_provider = ai_provider
    application.state.ai_request_options = ai_request_options

    application.add_middleware(RequestIdMiddleware)

    register_exception_handlers(application)

    application.include_router(router)

    return application


app = create_app()
