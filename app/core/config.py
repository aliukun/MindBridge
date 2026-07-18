from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """MindBridge 集中配置"""

    app_name: str = "MindBridge Learn"
    app_version: str = "0.6.0"
    environment: str = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    server_host: str = "127.0.0.1"
    server_port: int = 8000

    database_url: str = "sqlite:///./data/mindbridge.db"

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


@lru_cache
def get_settings() -> Settings:
    """返回全局复用的配置对象"""

    return Settings()
