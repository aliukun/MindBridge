from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """MindBridge 集中配置"""

    app_name: str = "MindBridge Learn"
    app_version: str = "0.7.0"
    environment: str = "development"
    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    server_host: str = "127.0.0.1"
    server_port: int = 8000

    database_url: str = "sqlite:///./data/mindbridge.db"

    ai_provider: str = "mock"
    ai_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        allow_inf_nan=False,
    )
    ai_max_tokens: int = Field(
        default=512,
        ge=1,
        le=4096,
    )

    bootstrap_student_username: str = "student"
    bootstrap_student_display_name: str = "Student"
    bootstrap_student_password: SecretStr | None = None

    bootstrap_admin_username: str = "admin"
    bootstrap_admin_display_name: str = "Administrator"
    bootstrap_admin_password: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ai_provider")
    @classmethod
    def normalize_ai_provider(
        cls,
        value: str,
    ) -> str:
        """统一 Provider 名称，拒绝空白配置。"""

        normalized = value.strip().casefold()

        if not normalized:
            raise ValueError("AI provider must not be blank.")

        return normalized


@lru_cache
def get_settings() -> Settings:
    """返回全局复用的配置对象"""

    return Settings()
