from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.ai.factory import (
    build_ai_provider,
    build_ai_request_options,
    validate_ai_provider_settings,
)
from app.ai.providers.http_support import build_http_timeout
from app.api.routes import router
from app.core.bootstrap import bootstrap_database
from app.core.config import Settings, get_settings
from app.core.errors import (
    RequestIdMiddleware,
    register_exception_handlers,
)
from app.core.logging import configure_logging


def create_lifespan(
    settings: Settings,
    *,
    http_transport: httpx.AsyncBaseTransport | None = None,
):
    """创建绑定当前配置和测试 Transport 的应用生命周期。"""

    @asynccontextmanager
    async def lifespan(
        application: FastAPI,
    ) -> AsyncIterator[None]:
        bootstrap_database()

        async with httpx.AsyncClient(
            timeout=build_http_timeout(settings),
            follow_redirects=False,
            transport=http_transport,
        ) as http_client:
            application.state.http_client = http_client
            application.state.ai_provider = build_ai_provider(
                settings,
                http_client=http_client,
            )

            yield

    return lifespan


def create_app(
    *,
    settings: Settings | None = None,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """创建并配置一个 FastAPI 应用实例。"""

    current_settings = settings or get_settings()

    validate_ai_provider_settings(current_settings)
    configure_logging(current_settings)

    application = FastAPI(
        title=current_settings.app_name,
        version=current_settings.app_version,
        lifespan=create_lifespan(
            current_settings,
            http_transport=http_transport,
        ),
    )

    application.state.settings = current_settings
    application.state.ai_request_options = build_ai_request_options(current_settings)

    application.add_middleware(RequestIdMiddleware)

    register_exception_handlers(application)

    application.include_router(router)

    return application


app = create_app()
