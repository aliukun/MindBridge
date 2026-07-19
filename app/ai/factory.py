import httpx

from app.ai.contracts import AiRequestOptions
from app.ai.errors import AiConfigurationError
from app.ai.providers.base import AiProvider
from app.ai.providers.mock import DeterministicMockProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import OpenAiCompatibleProvider
from app.core.config import Settings

SUPPORTED_AI_PROVIDERS = (
    "mock",
    "ollama",
    "openai_compatible",
)


def validate_ai_provider_settings(
    settings: Settings,
) -> None:
    """在应用构造阶段同步验证 Provider 专属配置。"""

    provider_name = settings.ai_provider

    if provider_name not in SUPPORTED_AI_PROVIDERS:
        supported = ", ".join(SUPPORTED_AI_PROVIDERS)

        raise AiConfigurationError(
            (
                f"Unsupported AI provider {provider_name!r}. "
                f"Supported providers: {supported}."
            )
        ) from None

    if provider_name != "openai_compatible":
        return

    if (
        settings.openai_compatible_base_url is None
        or settings.openai_compatible_model is None
        or settings.openai_compatible_api_key is None
    ):
        raise AiConfigurationError(
            "OpenAI-compatible provider configuration is incomplete."
        ) from None

    if not settings.openai_compatible_api_key.get_secret_value().strip():
        raise AiConfigurationError(
            "OpenAI-compatible API key must not be blank."
        ) from None


def build_ai_provider(
    settings: Settings,
    *,
    http_client: httpx.AsyncClient,
) -> AiProvider:
    """使用共享 HTTP 客户端构造显式选择的 Provider。"""

    validate_ai_provider_settings(settings)

    if settings.ai_provider == "mock":
        return DeterministicMockProvider()

    if settings.ai_provider == "ollama":
        return OllamaProvider(
            http_client=http_client,
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            total_timeout_seconds=(settings.ai_total_timeout_seconds),
        )

    if settings.ai_provider == "openai_compatible":
        base_url = settings.openai_compatible_base_url
        api_key = settings.openai_compatible_api_key
        model = settings.openai_compatible_model

        if base_url is None or api_key is None or model is None:
            raise AiConfigurationError(
                "OpenAI-compatible provider configuration is incomplete."
            ) from None

        return OpenAiCompatibleProvider(
            http_client=http_client,
            base_url=base_url,
            api_key=api_key,
            model=model,
            total_timeout_seconds=(settings.ai_total_timeout_seconds),
        )

    raise AiConfigurationError(
        f"Unsupported AI provider {settings.ai_provider!r}."
    ) from None


def build_ai_request_options(
    settings: Settings,
) -> AiRequestOptions:
    """把集中配置转换成不可变的 AI 请求选项。"""

    return AiRequestOptions(
        temperature=settings.ai_temperature,
        max_tokens=settings.ai_max_tokens,
    )
