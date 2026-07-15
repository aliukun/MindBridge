from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, StaticPool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 实体的共同基类。"""

    pass


def _ensure_sqlite_directory(database_url: str) -> None:
    """使用文件型 SQLite 时，自动创建数据库所在目录。"""

    if not database_url.startswith("sqlite"):
        return

    if ":memory:" in database_url:
        return

    if "///" not in database_url:
        return

    path_text = database_url.split("///", maxsplit=1)[1]
    path_text = path_text.split("?", maxsplit=1)[0]

    database_path = Path(path_text)
    database_path.parent.mkdir(parents=True, exist_ok=True)


def build_engine(database_url: str) -> Engine:
    """根据数据库连接地址创建 SQLAlchemy Engine。"""

    _ensure_sqlite_directory(database_url)

    if database_url.startswith("sqlite"):
        if ":memory:" in database_url:
            return create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )

        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


settings = get_settings()

engine = build_engine(settings.database_url)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """为一次业务操作或一次 HTTP 请求提供数据库 Session。"""

    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()