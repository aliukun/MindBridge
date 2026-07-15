from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.entities import ROLE_USER, ROLE_ADMIN, UserAccount

ALLOWED_ROLES = {
    ROLE_USER,
    ROLE_ADMIN,
}

def get_user_by_username(
        database: Session,
        username: str,
) -> UserAccount | None:
    """按用户名查询账户"""

    statement = select(UserAccount).where(
        UserAccount.username == username,
    )

    return database.scalars(statement).one_or_none()

def create_user(
        database: Session,
        *,
        username: str,
        display_name: str,
        password: str,
        roles: Iterable[str] = (ROLE_USER,),
) -> UserAccount:
    """创建用户，但由调用方决定何时提交事务"""

    username = username.strip()
    display_name = display_name.strip()

    if not username:
        raise ValueError("Username must not be empty.")

    if not username.isascii():
        raise ValueError("Username must contain ASCII characters only.")

    if len(username) > 64:
        raise ValueError("Username must not exceed 64 characters.")

    if not display_name:
        raise ValueError("Display name must not be empty.")

    if len(display_name) > 128:
        raise ValueError("Display name must not exceed 128 characters.")

    if get_user_by_username(
        database,
        username,
    ) is not None:
        raise ValueError(f"Username already exists: {username}")

    normalized_roles = {
        role.strip()
        for role in roles
        if role.strip()
    }

    unknown_roles = (
        normalized_roles - ALLOWED_ROLES
    )

    if unknown_roles:
        raise ValueError(f"Unknown roles: {sorted(unknown_roles)}")

    normalized_roles.add(ROLE_USER)

    user = UserAccount(
        username = username,
        display_name = display_name,
        password_hash = hash_password(password)
    )

    user.roles = normalized_roles

    database.add(user)
    database.flush()

    return user

def ensure_user(
        database: Session,
        *,
        username: str,
        display_name: str,
        password: str,
        roles: Iterable[str],
) -> UserAccount:
    """用户不存在时创建，已经存在时直接返回"""

    existing_user = get_user_by_username(
        database,
        username
    )

    if existing_user is not None:
        return existing_user

    return create_user(
        database,
        username=username,
        display_name=display_name,
        password=password,
        roles=roles,
    )