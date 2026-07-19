from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AiProviderName = Literal[
    "mock",
    "ollama",
    "openai_compatible",
]


def _normalize_http_base_url(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = value.strip().rstrip("/")

    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")

    if any(character.isspace() for character in normalized):
        raise ValueError(f"{field_name} must not contain whitespace.")

    try:
        parsed = urlsplit(normalized)
        _ = parsed.port
    except ValueError as error:
        raise ValueError(f"{field_name} is not a valid URL.") from error

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{field_name} must be an HTTP or HTTPS URL with a host.")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} must not contain credentials.")

    if parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} must not contain a query or fragment.")

    return normalized


class Settings(BaseSettings):
    """MindBridge 集中配置。"""

    app_name: str = "MindBridge Learn"
    app_version: str = "0.9.0"
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

    ai_provider: AiProviderName = "mock"
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
    ai_connect_timeout_seconds: float = Field(
        default=5.0,
        gt=0.0,
        le=60.0,
        allow_inf_nan=False,
    )
    ai_read_timeout_seconds: float = Field(
        default=60.0,
        gt=0.0,
        le=300.0,
        allow_inf_nan=False,
    )
    ai_total_timeout_seconds: float = Field(
        default=120.0,
        gt=0.0,
        le=600.0,
        allow_inf_nan=False,
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "mindbridge-qwen2.5-7b-ft:latest"

    finetuned_model_dir: Path = Path("models/mindbridge-qwen2.5-7b-ft")
    finetuned_model_file: str = "mindbridge-qwen2.5-7b-ft-q4_k_m.gguf"

    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: SecretStr | None = None
    openai_compatible_model: str | None = None

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

    @field_validator("ai_provider", mode="before")
    @classmethod
    def normalize_ai_provider(
        cls,
        value: object,
    ) -> object:
        """在 Literal 校验前统一大小写和首尾空白。"""

        if not isinstance(value, str):
            return value

        normalized = value.strip().casefold()

        if not normalized:
            raise ValueError("AI provider must not be blank.")

        return normalized

    @field_validator(
        "ollama_base_url",
        "openai_compatible_base_url",
        mode="before",
    )
    @classmethod
    def normalize_base_urls(
        cls,
        value: object,
        info,
    ) -> object:
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        return _normalize_http_base_url(
            value,
            field_name=info.field_name,
        )

    @field_validator(
        "ollama_model",
        "openai_compatible_model",
    )
    @classmethod
    def normalize_model_names(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError("AI model name must not be blank.")

        if len(normalized) > 256:
            raise ValueError("AI model name must not exceed 256 characters.")

        return normalized

    @field_validator("finetuned_model_dir")
    @classmethod
    def validate_model_directory(
        cls,
        value: Path,
    ) -> Path:
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("Fine-tuned model directory must be project-relative.")

        if not value.parts or value.parts[0].casefold() != "models":
            raise ValueError("Fine-tuned model directory must be inside models/.")

        return value

    @field_validator("finetuned_model_file")
    @classmethod
    def validate_model_filename(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized or Path(normalized).name != normalized:
            raise ValueError("Fine-tuned model file must be a plain filename.")

        if Path(normalized).suffix.casefold() != ".gguf":
            raise ValueError("Fine-tuned model file must use the .gguf suffix.")

        return normalized

    @model_validator(mode="after")
    def validate_provider_specific_settings(self) -> Self:
        if self.ai_provider != "openai_compatible":
            return self

        if self.openai_compatible_base_url is None:
            raise ValueError(
                "OPENAI_COMPATIBLE_BASE_URL is required for openai_compatible."
            )

        if self.openai_compatible_model is None:
            raise ValueError(
                "OPENAI_COMPATIBLE_MODEL is required for openai_compatible."
            )

        if self.openai_compatible_api_key is None:
            raise ValueError(
                "OPENAI_COMPATIBLE_API_KEY is required for openai_compatible."
            )

        if not self.openai_compatible_api_key.get_secret_value().strip():
            raise ValueError("OPENAI_COMPATIBLE_API_KEY must not be blank.")

        return self


@lru_cache
def get_settings() -> Settings:
    """返回全局复用的配置对象。"""

    return Settings()
