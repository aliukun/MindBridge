import logging
import re
import traceback
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr

from app.core.config import Settings

REDACTED = "[REDACTED]"

_AUTHORIZATION_PATTERN = re.compile(
    r"\b(Basic|Bearer)\s+[^\s,;}\]\"']+",
    flags=re.IGNORECASE,
)

_DATABASE_CREDENTIALS_PATTERN = re.compile(
    r"(?P<prefix>[a-z][a-z0-9+.-]*://[^:/@\s]+:)"
    r"[^@\s/]+(?=@)",
    flags=re.IGNORECASE,
)

_LABELED_SECRET_PATTERN = re.compile(
    r"""
    (?P<label>
        [\"']?
        (?:
            authorization
            | proxy[-_]?authorization
            | password
            | passwd
            | passphrase
            | api[-_]?key
            | access[-_]?token
            | refresh[-_]?token
            | secret
            | token
        )
        [\"']?
        \s*[:=]\s*
    )
    (?P<value>
        \"[^\"\r\n]*\"
        | '[^'\r\n]*'
        | [^\s,;}\]]+
    )
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def redact_text(
    text: str,
    *,
    secret_values: Iterable[str] = (),
) -> str:
    """遮盖日志文本中已知的秘密和常见凭据格式。"""

    redacted = text

    known_secrets = sorted(
        {secret for secret in secret_values if secret},
        key=len,
        reverse=True,
    )

    for secret in known_secrets:
        redacted = redacted.replace(
            secret,
            REDACTED,
        )

    redacted = _DATABASE_CREDENTIALS_PATTERN.sub(
        rf"\g<prefix>{REDACTED}",
        redacted,
    )

    redacted = _AUTHORIZATION_PATTERN.sub(
        rf"\1 {REDACTED}",
        redacted,
    )

    redacted = _LABELED_SECRET_PATTERN.sub(
        lambda match: f"{match.group('label')}{REDACTED}",
        redacted,
    )

    return redacted


class SafeFormatter(logging.Formatter):
    """在日志完成渲染后脱敏，并隐藏异常消息正文。"""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
        *,
        secret_values: Iterable[str] = (),
    ) -> None:
        super().__init__(
            fmt=fmt,
            datefmt=datefmt,
            style=style,
            validate=validate,
        )

        self._secret_values = tuple(secret for secret in secret_values if secret)

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)

        return redact_text(
            rendered,
            secret_values=self._secret_values,
        )

    def formatException(
        self,
        exc_info: tuple[
            type[BaseException],
            BaseException,
            TracebackType | None,
        ]
        | tuple[None, None, None],
    ) -> str:
        """只保留异常类型和栈位置，不记录异常消息与源码行。"""

        exception_type, _, traceback_object = exc_info

        if exception_type is None:
            return ""

        lines = [
            "Traceback (most recent call last):\n",
        ]

        if traceback_object is not None:
            for frame in traceback.extract_tb(
                traceback_object,
            ):
                filename = Path(frame.filename).name

                lines.append(
                    (f'  File "{filename}", line {frame.lineno}, in {frame.name}\n')
                )

        lines.append((f"{exception_type.__module__}.{exception_type.__qualname__}"))

        return redact_text(
            "".join(lines),
            secret_values=self._secret_values,
        )


def _settings_secret_values(
    settings: Settings,
) -> tuple[str, ...]:
    """收集配置中的 SecretStr 和数据库 URL 密码。"""

    secrets: list[str] = []

    for field_name in type(settings).model_fields:
        value = getattr(settings, field_name)

        if isinstance(value, SecretStr):
            secret = value.get_secret_value()

            if secret:
                secrets.append(secret)

    try:
        database_password = urlsplit(settings.database_url).password
    except ValueError:
        database_password = None

    if database_password:
        secrets.append(database_password)

    return tuple(secrets)


def configure_logging(settings: Settings) -> None:
    """为 MindBridge 应用日志安装一个可重复配置的安全处理器。"""

    application_logger = logging.getLogger("app")

    level_name = str(getattr(settings, "log_level", "INFO")).upper()

    level = getattr(
        logging,
        level_name,
        logging.INFO,
    )

    application_logger.setLevel(level)
    application_logger.propagate = False

    for handler in list(application_logger.handlers):
        if getattr(
            handler,
            "_mindbridge_safe_handler",
            False,
        ):
            application_logger.removeHandler(handler)
            handler.close()

    console_handler = logging.StreamHandler()
    setattr(
        console_handler,
        "_mindbridge_safe_handler",
        True,
    )

    console_handler.setFormatter(
        SafeFormatter(
            fmt=("%(asctime)s %(levelname)s %(name)s %(message)s"),
            secret_values=_settings_secret_values(settings),
        )
    )

    application_logger.addHandler(console_handler)
