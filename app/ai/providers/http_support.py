from collections.abc import AsyncIterator
from typing import NoReturn

import httpx

from app.ai.contracts import AiFinishReason
from app.ai.errors import (
    AiAuthenticationError,
    AiModelNotFoundError,
    AiProtocolError,
    AiRateLimitError,
    AiResponseError,
    AiTimeoutError,
    AiUnavailableError,
)
from app.core.config import Settings


def build_http_timeout(settings: Settings) -> httpx.Timeout:
    """把集中配置转换成 HTTPX 的分阶段超时。"""

    return httpx.Timeout(
        connect=settings.ai_connect_timeout_seconds,
        read=settings.ai_read_timeout_seconds,
        write=settings.ai_read_timeout_seconds,
        pool=settings.ai_connect_timeout_seconds,
    )


def join_provider_url(
    base_url: str,
    path: str,
) -> str:
    """保留 base URL 中的 /v1 等前缀，再追加接口路径。"""

    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def raise_for_provider_status(
    response: httpx.Response,
    *,
    provider_name: str,
    not_found_is_model: bool = True,
) -> None:
    """将 HTTP 状态映射成稳定、不会包含响应正文的 AI 异常。"""

    status_code = response.status_code

    if 200 <= status_code < 300:
        return

    if status_code in {401, 403}:
        raise AiAuthenticationError(
            f"{provider_name} rejected the configured credentials."
        ) from None

    if status_code == 404 and not_found_is_model:
        raise AiModelNotFoundError(
            f"{provider_name} could not find the configured model."
        ) from None

    if status_code in {408, 504}:
        raise AiTimeoutError(
            f"{provider_name} timed out while processing the request."
        ) from None

    if status_code == 429:
        raise AiRateLimitError(
            f"{provider_name} rejected the request because of rate limits."
        ) from None

    if status_code >= 500:
        raise AiUnavailableError(f"{provider_name} is currently unavailable.") from None

    raise AiResponseError(f"{provider_name} returned HTTP {status_code}.") from None


def raise_timeout(provider_name: str) -> NoReturn:
    """抛出不携带底层 URL 或正文的稳定超时异常。"""

    raise AiTimeoutError(f"{provider_name} request timed out.") from None


def raise_unavailable(provider_name: str) -> NoReturn:
    """抛出不携带底层网络异常消息的稳定不可用异常。"""

    raise AiUnavailableError(f"{provider_name} is currently unavailable.") from None


def raise_request_error(
    error: httpx.RequestError,
    *,
    provider_name: str,
) -> NoReturn:
    """区分连接不可用、读取超时和传输协议损坏。"""

    if isinstance(error, httpx.TimeoutException):
        raise_timeout(provider_name)

    if isinstance(
        error,
        (httpx.ProtocolError, httpx.DecodingError),
    ):
        raise AiProtocolError(
            f"{provider_name} connection ended with invalid protocol data."
        ) from None

    raise_unavailable(provider_name)


def response_json_object(
    response: httpx.Response,
    *,
    provider_name: str,
) -> dict[str, object]:
    """只接受 JSON object；坏 JSON 和顶层数组都属于协议错误。"""

    try:
        payload = response.json()
    except (ValueError, UnicodeDecodeError):
        raise AiProtocolError(f"{provider_name} returned invalid JSON.") from None

    if not isinstance(payload, dict):
        raise AiProtocolError(
            f"{provider_name} returned a non-object JSON payload."
        ) from None

    return payload


async def iter_sse_data(
    response: httpx.Response,
) -> AsyncIterator[str]:
    """按 SSE 空行边界合并 data 字段，忽略注释和其他字段。"""

    data_lines: list[str] = []

    async for line in response.aiter_lines():
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines.clear()

            continue

        if line.startswith(":"):
            continue

        field, separator, value = line.partition(":")

        if not separator or field != "data":
            continue

        if value.startswith(" "):
            value = value[1:]

        data_lines.append(value)

    if data_lines:
        yield "\n".join(data_lines)


def parse_finish_reason(
    value: object,
    *,
    provider_name: str,
) -> AiFinishReason:
    """把供应商停止原因缩小为项目支持的稳定枚举。"""

    if value == "stop":
        return AiFinishReason.STOP

    if value == "length":
        return AiFinishReason.LENGTH

    raise AiProtocolError(
        f"{provider_name} returned an unsupported finish reason."
    ) from None
