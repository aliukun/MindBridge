from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal, engine
from app.core.schema import ensure_schema
from app.models import entities  # noqa: F401
from app.models.entities import ROLE_ADMIN, ROLE_USER
from app.services.user_service import ensure_user


def create_schema(bind: Engine = engine) -> None:
    """为空库建表，或只读确认已有结构兼容。"""

    ensure_schema(bind)


def initialize_users(
    database: Session,
    settings: Settings,
) -> None:
    """根据配置创建初始学生和管理员"""

    user_specs = (
        (
            settings.bootstrap_student_username,
            settings.bootstrap_student_display_name,
            settings.bootstrap_student_password,
            {ROLE_USER},
        ),
        (
            settings.bootstrap_admin_username,
            settings.bootstrap_admin_display_name,
            settings.bootstrap_admin_password,
            {ROLE_USER, ROLE_ADMIN},
        ),
    )

    for username, display_name, secret, roles in user_specs:
        if secret is None:
            continue

        password = secret.get_secret_value()

        if not password:
            continue

        ensure_user(
            database,
            username=username,
            display_name=display_name,
            password=password,
            roles=roles,
        )


def bootstrap_database() -> None:
    """建表并初始化配置中启用的用户"""

    create_schema()

    settings = get_settings()

    with SessionLocal() as database:
        initialize_users(database, settings)

        database.commit()
