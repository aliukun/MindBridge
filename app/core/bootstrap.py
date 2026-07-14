from sqlalchemy.engine import Engine

from app.core.database import Base, engine
from app.models import entities  # noqa: F401


def create_schema(bind: Engine = engine) -> None:
    """创建当前尚不存在的数据库表。"""

    Base.metadata.create_all(bind=bind)