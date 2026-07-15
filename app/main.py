from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.bootstrap import create_schema, bootstrap_database
from app.core.config import get_settings

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """管理应用启动和关闭期间需要执行的操作"""

    bootstrap_database()

    yield

def create_app() -> FastAPI:
    """创建并配置一个 FastAPI 应用实例"""

    settings = get_settings()

    application = FastAPI(
        title = settings.app_name,
        version = settings.app_version,
        lifespan = lifespan,
    )

    application.include_router(router)

    return application

app = create_app()