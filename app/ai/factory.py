from app.ai.contracts import AiRequestOptions
from app.ai.errors import AiConfigurationError
from app.ai.providers.base import AiProvider
from app.ai.providers.mock import DeterministicMockProvider
from app.core.config import Settings


def build_ai_provider(
    provider_name: str,
) -> AiProvider:
    """根据显式名称构造 Provider，未知名称绝不回退。"""

    normalized = provider_name.strip().casefold()

    if normalized == "mock":
        return DeterministicMockProvider()

    raise AiConfigurationError(
        (f"Unsupported AI provider {provider_name!r}. Supported providers: mock.")
    ) from None


def build_ai_request_options(
    settings: Settings,
) -> AiRequestOptions:
    """把集中配置转换成不可变的 AI 请求选项。"""

    return AiRequestOptions(
        temperature=settings.ai_temperature,
        max_tokens=settings.ai_max_tokens,
    )
