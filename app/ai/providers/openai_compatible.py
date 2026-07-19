import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from app.ai.contracts import (
    MAX_AI_COMPLETION_LENGTH,
    MAX_AI_STREAM_DELTA_LENGTH,
    AiCompletion,
    AiFinishReason,
    AiRequest,
    AiStreamChunk,
    ProviderState,
    ProviderStatus,
)
from app.ai.errors import (
    AiAuthenticationError,
    AiModelNotFoundError,
    AiProtocolError,
    AiProviderError,
)
from app.ai.providers.http_support import (
    iter_sse_data,
    join_provider_url,
    parse_finish_reason,
    raise_for_provider_status,
    raise_request_error,
    raise_timeout,
    response_json_object,
)

OPENAI_COMPATIBLE_PROVIDER_NAME = "openai_compatible"


def _chat_payload(
    request: AiRequest,
    *,
    model: str,
    stream: bool,
) -> dict[str, object]:
    return {
        "model": model,
        "messages": [message.model_dump(mode="json") for message in request.messages],
        "temperature": request.options.temperature,
        "max_tokens": request.options.max_tokens,
        "stream": stream,
    }


def _first_choice(
    payload: dict[str, object],
) -> dict[str, object]:
    choices = payload.get("choices")

    if not isinstance(choices, list) or not choices:
        raise AiProtocolError(
            "OpenAI-compatible response is missing choices."
        ) from None

    choice = choices[0]

    if not isinstance(choice, dict):
        raise AiProtocolError(
            "OpenAI-compatible response contains an invalid choice."
        ) from None

    return choice


class OpenAiCompatibleProvider:
    """调用遵循 Chat Completions 形状的兼容服务。"""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        api_key: SecretStr,
        model: str,
        total_timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._total_timeout_seconds = total_timeout_seconds

    @property
    def name(self) -> str:
        return OPENAI_COMPATIBLE_PROVIDER_NAME

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": (f"Bearer {self._api_key.get_secret_value()}"),
            "Content-Type": "application/json",
        }

    async def complete(
        self,
        request: AiRequest,
    ) -> AiCompletion:
        url = join_provider_url(
            self._base_url,
            "/chat/completions",
        )

        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                response = await self._http_client.post(
                    url,
                    headers=self._headers(),
                    json=_chat_payload(
                        request,
                        model=self._model,
                        stream=False,
                    ),
                )
        except (TimeoutError, httpx.TimeoutException):
            raise_timeout("OpenAI-compatible provider")
        except httpx.RequestError as error:
            raise_request_error(
                error,
                provider_name="OpenAI-compatible provider",
            )

        raise_for_provider_status(
            response,
            provider_name="OpenAI-compatible provider",
        )
        payload = response_json_object(
            response,
            provider_name="OpenAI-compatible provider",
        )
        choice = _first_choice(payload)
        message = choice.get("message")

        if not isinstance(message, dict):
            raise AiProtocolError(
                "OpenAI-compatible response is missing the message object."
            ) from None

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise AiProtocolError(
                "OpenAI-compatible response contains an empty completion."
            ) from None

        if len(content) > MAX_AI_COMPLETION_LENGTH:
            raise AiProtocolError(
                "OpenAI-compatible completion exceeds the safety limit."
            ) from None

        return AiCompletion(
            text=content,
            provider=self.name,
            model=self._model,
            finish_reason=parse_finish_reason(
                choice.get("finish_reason"),
                provider_name="OpenAI-compatible provider",
            ),
        )

    def stream(
        self,
        request: AiRequest,
    ) -> AsyncIterator[AiStreamChunk]:
        async def generate() -> AsyncIterator[AiStreamChunk]:
            url = join_provider_url(
                self._base_url,
                "/chat/completions",
            )
            chunk_index = 0
            total_characters = 0
            finish_reason: AiFinishReason | None = None

            try:
                async with asyncio.timeout(self._total_timeout_seconds):
                    async with self._http_client.stream(
                        "POST",
                        url,
                        headers=self._headers(),
                        json=_chat_payload(
                            request,
                            model=self._model,
                            stream=True,
                        ),
                    ) as response:
                        raise_for_provider_status(
                            response,
                            provider_name="OpenAI-compatible provider",
                        )

                        async for data in iter_sse_data(response):
                            data = data.strip()

                            if data == "[DONE]":
                                if finish_reason is None:
                                    raise AiProtocolError(
                                        "OpenAI-compatible stream ended without a finish reason."
                                    ) from None

                                if total_characters == 0:
                                    raise AiProtocolError(
                                        "OpenAI-compatible stream completed without text."
                                    ) from None

                                yield AiStreamChunk(
                                    index=chunk_index,
                                    done=True,
                                    finish_reason=finish_reason,
                                )
                                return

                            try:
                                payload = json.loads(data)
                            except json.JSONDecodeError:
                                raise AiProtocolError(
                                    "OpenAI-compatible stream contains invalid JSON."
                                ) from None

                            if not isinstance(payload, dict):
                                raise AiProtocolError(
                                    "OpenAI-compatible stream contains a non-object event."
                                ) from None

                            choice = _first_choice(payload)
                            delta = choice.get("delta")

                            if not isinstance(delta, dict):
                                raise AiProtocolError(
                                    "OpenAI-compatible stream is missing the delta object."
                                ) from None

                            content = delta.get("content")

                            if content is not None and not isinstance(
                                content,
                                str,
                            ):
                                raise AiProtocolError(
                                    "OpenAI-compatible stream has invalid content."
                                ) from None

                            if content:
                                total_characters += len(content)

                                if (
                                    len(content) > MAX_AI_STREAM_DELTA_LENGTH
                                    or total_characters > MAX_AI_COMPLETION_LENGTH
                                ):
                                    raise AiProtocolError(
                                        "OpenAI-compatible stream exceeds the safety limit."
                                    ) from None

                                yield AiStreamChunk(
                                    index=chunk_index,
                                    delta=content,
                                )
                                chunk_index += 1

                            raw_finish_reason = choice.get("finish_reason")

                            if raw_finish_reason is not None:
                                parsed_finish_reason = parse_finish_reason(
                                    raw_finish_reason,
                                    provider_name="OpenAI-compatible provider",
                                )

                                if (
                                    finish_reason is not None
                                    and finish_reason is not parsed_finish_reason
                                ):
                                    raise AiProtocolError(
                                        "OpenAI-compatible stream changed its finish reason."
                                    ) from None

                                finish_reason = parsed_finish_reason
            except (TimeoutError, httpx.TimeoutException):
                raise_timeout("OpenAI-compatible provider")
            except httpx.RequestError as error:
                raise_request_error(
                    error,
                    provider_name="OpenAI-compatible provider",
                )

            raise AiProtocolError(
                "OpenAI-compatible stream ended before [DONE]."
            ) from None

        return generate()

    async def status(self) -> ProviderStatus:
        model_path = f"/models/{quote(self._model, safe='')}"
        url = join_provider_url(
            self._base_url,
            model_path,
        )

        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                response = await self._http_client.get(
                    url,
                    headers=self._headers(),
                )

            raise_for_provider_status(
                response,
                provider_name="OpenAI-compatible provider",
            )
            payload = response_json_object(
                response,
                provider_name="OpenAI-compatible provider",
            )

            if payload.get("id") != self._model:
                raise AiProtocolError(
                    "OpenAI-compatible model status returned an unexpected model."
                ) from None
        except AiAuthenticationError:
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.MISCONFIGURED,
                model=self._model,
                detail="OpenAI-compatible credentials were rejected.",
            )
        except AiModelNotFoundError:
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.MODEL_NOT_FOUND,
                model=self._model,
                detail="The configured model was not found.",
            )
        except (TimeoutError, httpx.TimeoutException):
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.UNAVAILABLE,
                model=self._model,
                detail="OpenAI-compatible model status timed out.",
            )
        except httpx.RequestError:
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.UNAVAILABLE,
                model=self._model,
                detail="OpenAI-compatible service is unavailable.",
            )
        except AiProviderError:
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.UNAVAILABLE,
                model=self._model,
                detail="OpenAI-compatible model status is unavailable.",
            )

        return ProviderStatus(
            provider=self.name,
            state=ProviderState.READY,
            model=self._model,
            detail="OpenAI-compatible service and model are ready.",
        )
