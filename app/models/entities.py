from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserAccount(Base):
    """系统用户账户。"""

    __tablename__ = "user_accounts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(128),
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
    )

    roles_csv: Mapped[str] = mapped_column(
        String(256),
        default="ROLE_USER",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    @property
    def roles(self) -> list[str]:
        """把数据库中的逗号分隔角色转换成 Python 列表。"""

        return [
            role
            for role in (self.roles_csv or "").split(",")
            if role
        ]

    @roles.setter
    def roles(self, value: list[str] | set[str]) -> None:
        """把 Python 角色集合转换成数据库字符串。"""

        self.roles_csv = ",".join(sorted(value))