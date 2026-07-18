import sqlite3
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import StaticPool, create_engine, event
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


def _enable_sqlite_foreign_keys(
    dbapi_connection: object,
    _: object,
) -> None:
    """为每一个新 SQLite 连接启用外键约束。"""

    if not isinstance(dbapi_connection, sqlite3.Connection):
        return

    previous_autocommit = getattr(
        dbapi_connection,
        "autocommit",
        None,
    )

    if previous_autocommit is not None:
        dbapi_connection.autocommit = True

    try:
        cursor = dbapi_connection.cursor()

        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
    finally:
        if previous_autocommit is not None:
            dbapi_connection.autocommit = previous_autocommit


def _attach_sqlite_connection_rules(
    sqlite_engine: Engine,
) -> Engine:
    """把 SQLite 连接级规则绑定到指定 Engine。"""

    event.listen(
        sqlite_engine,
        "connect",
        _enable_sqlite_foreign_keys,
    )

    return sqlite_engine


def build_engine(database_url: str) -> Engine:
    """根据数据库连接地址创建 SQLAlchemy Engine。"""

    _ensure_sqlite_directory(database_url)

    if database_url.startswith("sqlite"):
        if ":memory:" in database_url:
            return _attach_sqlite_connection_rules(
                create_engine(
                    database_url,
                    echo=False,
                    hide_parameters=True,
                    connect_args={
                        "check_same_thread": False,
                    },
                    poolclass=StaticPool,
                )
            )

        return _attach_sqlite_connection_rules(
            create_engine(
                database_url,
                echo=False,
                hide_parameters=True,
                connect_args={
                    "check_same_thread": False,
                },
            )
        )

    return create_engine(
        database_url,
        echo=False,
        hide_parameters=True,
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
