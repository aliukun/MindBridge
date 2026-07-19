import re

PHONE_PLACEHOLDER = "[PHONE_REDACTED]"
EMAIL_PLACEHOLDER = "[EMAIL_REDACTED]"
NATIONAL_ID_PLACEHOLDER = "[NATIONAL_ID_REDACTED]"
CAMPUS_ID_PLACEHOLDER = "[CAMPUS_ID_REDACTED]"

_PHONE_PATTERN = re.compile(r"(?<![0-9])(?:\+?86[\s-]?)?1[3-9][0-9]{9}(?![0-9])")

_EMAIL_PATTERN = re.compile(
    (
        r"(?<![A-Za-z0-9._%+-])"
        r"[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
        r"(?![A-Za-z0-9._%+-])"
    )
)

_NATIONAL_ID_PATTERN = re.compile(
    (
        r"(?<![0-9A-Za-z])"
        r"(?:[0-9]{17}[0-9Xx]|[0-9]{15})"
        r"(?![0-9A-Za-z])"
    )
)

_LABELED_CAMPUS_ID_PATTERN = re.compile(
    (
        r"(?:学号|student[\s_-]*id(?![A-Za-z]))"
        r"\s*(?:是\s*)?(?:[:：=]\s*)?"
        r"[A-Za-z0-9][A-Za-z0-9-]{5,23}"
    ),
    re.IGNORECASE,
)


class PrivacySanitizer:
    """为离开业务数据库的数据创建不可逆的脱敏副本。"""

    def __init__(
        self,
        *,
        extra_campus_id_patterns: tuple[re.Pattern[str], ...] = (),
    ) -> None:
        self._campus_id_patterns = (
            _LABELED_CAMPUS_ID_PATTERN,
            *extra_campus_id_patterns,
        )

    def sanitize(self, text: str) -> str:
        """替换敏感标识，不修改调用者持有的原始字符串。"""

        sanitized = text

        for pattern in self._campus_id_patterns:
            sanitized = pattern.sub(
                CAMPUS_ID_PLACEHOLDER,
                sanitized,
            )

        sanitized = _NATIONAL_ID_PATTERN.sub(
            NATIONAL_ID_PLACEHOLDER,
            sanitized,
        )
        sanitized = _PHONE_PATTERN.sub(
            PHONE_PLACEHOLDER,
            sanitized,
        )
        sanitized = _EMAIL_PATTERN.sub(
            EMAIL_PLACEHOLDER,
            sanitized,
        )

        return sanitized


_DEFAULT_SANITIZER = PrivacySanitizer()


def sanitize_for_ai(text: str) -> str:
    """使用默认规则生成发送给 AI 的文本。"""

    return _DEFAULT_SANITIZER.sanitize(text)
