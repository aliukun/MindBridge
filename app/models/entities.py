from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

ROLE_USER = "ROLE_USER"
ROLE_ADMIN = "ROLE_ADMIN"

MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"


def utc_now() -> datetime:
    """返回当前 UTC 时间"""

    return datetime.now(timezone.utc)


def new_public_id() -> str:
    """生成可以安全暴露给客户端的随机 UUID"""

    return str(uuid4())


class UserAccount(Base):
    """系统用户账户"""

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
        default=ROLE_USER,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    sessions: Mapped[list[ChatSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def roles(self) -> list[str]:
        """把数据库中的逗号分隔角色转换成 Python 列表"""

        return [role for role in (self.roles_csv or "").split(",") if role]

    @roles.setter
    def roles(
        self,
        value: list[str] | set[str],
    ) -> None:
        """清理、排序并保存角色"""

        cleaned_roles = {role.strip() for role in value if role.strip()}

        self.roles_csv = ",".join(sorted(cleaned_roles))


class ChatSession(Base):
    """一次聊天会话，并且只属于一个用户"""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    public_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=new_public_id,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "user_accounts.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    title: Mapped[str] = mapped_column(String(160))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    user: Mapped[UserAccount] = relationship(
        back_populates="sessions",
    )

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.id",
    )

    def touch(self) -> None:
        """有新消息时更新会话的最后修改时间"""

        self.updated_at = utc_now()


class ChatMessage(Base):
    """聊天会话中的一条用户消息或助手消息"""

    __tablename__ = "chat_messages"

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chat_messages_role",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chat_sessions.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    role: Mapped[str] = mapped_column(String(16))

    content: Mapped[str] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    session: Mapped[ChatSession] = relationship(
        back_populates="messages",
    )

    assessment_report: Mapped[PsychologicalReport | None] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class PsychologicalReport(Base):
    """中、高风险消息对应的后台心理安全报告。"""

    __tablename__ = "psychological_reports"

    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('MEDIUM', 'HIGH')",
            name="ck_psychological_reports_risk_level",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    message_id: Mapped[int] = mapped_column(
        ForeignKey(
            "chat_messages.id",
            ondelete="CASCADE",
        ),
        unique=True,
        index=True,
    )

    risk_level: Mapped[str] = mapped_column(
        String(16),
        index=True,
    )

    matched_signals_csv: Mapped[str] = mapped_column(
        String(512),
        default="",
    )

    assessment_method: Mapped[str] = mapped_column(
        String(64),
    )

    summary: Mapped[str] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    message: Mapped[ChatMessage] = relationship(
        back_populates="assessment_report",
    )

    @property
    def matched_signals(self) -> list[str]:
        """把逗号分隔的信号类别转换成列表。"""

        return [signal for signal in self.matched_signals_csv.split(",") if signal]

    @matched_signals.setter
    def matched_signals(
        self,
        value: tuple[str, ...] | list[str],
    ) -> None:
        """清理、去重并持久化信号类别。"""

        cleaned_signals = {signal.strip() for signal in value if signal.strip()}

        self.matched_signals_csv = ",".join(sorted(cleaned_signals))
