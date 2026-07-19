import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.ai.contracts import (
    MAX_AI_COMPLETION_LENGTH,
    MAX_AI_STREAM_DELTA_LENGTH,
    AiCompletion,
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
    AiResponseError,
)
from app.ai.providers.http_support import (
    join_provider_url,
    parse_finish_reason,
    raise_for_provider_status,
    raise_request_error,
    raise_timeout,
    response_json_object,
)

OLLAMA_PROVIDER_NAME = "ollama"


def _chat_payload(
    request: AiRequest,
    *,
    model: str,
    stream: bool,
) -> dict[str, object]:
    return {
        "model": model,
        "messages": [message.model_dump(mode="json") for message in request.messages],
        "stream": stream,
        "options": {
            "temperature": request.options.temperature,
            "num_predict": request.options.max_tokens,
        },
    }


def _completion_text(
    payload: dict[str, object],
) -> str:
    message = payload.get("message")

    if not isinstance(message, dict):
        raise AiProtocolError(
            "Ollama response is missing the message object."
        ) from None

    content = message.get("content")

    if not isinstance(content, str) or not content.strip():
        raise AiProtocolError("Ollama response contains an empty completion.") from None

    if len(content) > MAX_AI_COMPLETION_LENGTH:
        raise AiProtocolError(
            "Ollama completion exceeds the configured safety limit."
        ) from None

    return content


async def fetch_ollama_models(
    http_client: httpx.AsyncClient,
    *,
    base_url: str,
    total_timeout_seconds: float,
) -> frozenset[str]:
    """读取 Ollama 已注册模型名，不执行推理。"""

    url = join_provider_url(base_url, "/api/tags")

    try:
        async with asyncio.timeout(total_timeout_seconds):
            response = await http_client.get(url)
    except (TimeoutError, httpx.TimeoutException):
        raise_timeout("Ollama")
    except httpx.RequestError as error:
        raise_request_error(
            error,
            provider_name="Ollama",
        )

    raise_for_provider_status(
        response,
        provider_name="Ollama",
        not_found_is_model=False,
    )

    payload = response_json_object(
        response,
        provider_name="Ollama",
    )
    models = payload.get("models")

    if not isinstance(models, list):
        raise AiProtocolError(
            "Ollama tags response is missing the models list."
        ) from None

    registered_names: set[str] = set()

    for model_entry in models:
        if not isinstance(model_entry, dict):
            raise AiProtocolError(
                "Ollama tags response contains an invalid model entry."
            ) from None

        name = model_entry.get("name")

        if not isinstance(name, str) or not name.strip():
            name = model_entry.get("model")

        if not isinstance(name, str) or not name.strip():
            raise AiProtocolError(
                "Ollama tags response contains a model without a name."
            ) from None

        registered_names.add(name.strip())

    return frozenset(registered_names)


class OllamaProvider:
    """通过 Ollama HTTP API 调用本地注册模型。"""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        model: str,
        total_timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._total_timeout_seconds = total_timeout_seconds

    @property
    def name(self) -> str:
        return OLLAMA_PROVIDER_NAME

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        request: AiRequest,
    ) -> AiCompletion:
        url = join_provider_url(
            self._base_url,
            "/api/chat",
        )

        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                response = await self._http_client.post(
                    url,
                    json=_chat_payload(
                        request,
                        model=self._model,
                        stream=False,
                    ),
                )
        except (TimeoutError, httpx.TimeoutException):
            raise_timeout("Ollama")
        except httpx.RequestError as error:
            raise_request_error(
                error,
                provider_name="Ollama",
            )

        raise_for_provider_status(
            response,
            provider_name="Ollama",
        )
        payload = response_json_object(
            response,
            provider_name="Ollama",
        )

        if payload.get("done") is not True:
            raise AiProtocolError(
                "Ollama non-streaming response is not marked done."
            ) from None

        return AiCompletion(
            text=_completion_text(payload),
            provider=self.name,
            model=self._model,
            finish_reason=parse_finish_reason(
                payload.get("done_reason"),
                provider_name="Ollama",
            ),
        )

    def stream(
        self,
        request: AiRequest,
    ) -> AsyncIterator[AiStreamChunk]:
        async def generate() -> AsyncIterator[AiStreamChunk]:
            url = join_provider_url(
                self._base_url,
                "/api/chat",
            )
            chunk_index = 0
            total_characters = 0

            try:
                async with asyncio.timeout(self._total_timeout_seconds):
                    async with self._http_client.stream(
                        "POST",
                        url,
                        json=_chat_payload(
                            request,
                            model=self._model,
                            stream=True,
                        ),
                    ) as response:
                        raise_for_provider_status(
                            response,
                            provider_name="Ollama",
                        )

                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue

                            try:
                                payload = json.loads(line)
                            except json.JSONDecodeError:
                                raise AiProtocolError(
                                    "Ollama stream contains invalid NDJSON."
                                ) from None

                            if not isinstance(payload, dict):
                                raise AiProtocolError(
                                    "Ollama stream contains a non-object event."
                                ) from None

                            done = payload.get("done")

                            if not isinstance(done, bool):
                                raise AiProtocolError(
                                    "Ollama stream event is missing the done flag."
                                ) from None

                            if not done and payload.get("done_reason") is not None:
                                raise AiProtocolError(
                                    "Ollama sent a finish reason before completion."
                                ) from None

                            message = payload.get("message")

                            if not isinstance(message, dict):
                                raise AiProtocolError(
                                    "Ollama stream event is missing the message object."
                                ) from None

                            content = message.get("content")

                            if not isinstance(content, str):
                                raise AiProtocolError(
                                    "Ollama stream event has invalid content."
                                ) from None

                            if content:
                                total_characters += len(content)

                                if (
                                    len(content) > MAX_AI_STREAM_DELTA_LENGTH
                                    or total_characters > MAX_AI_COMPLETION_LENGTH
                                ):
                                    raise AiProtocolError(
                                        "Ollama stream exceeds the configured safety limit."
                                    ) from None

                                yield AiStreamChunk(
                                    index=chunk_index,
                                    delta=content,
                                )
                                chunk_index += 1

                            if done:
                                if total_characters == 0:
                                    raise AiProtocolError(
                                        "Ollama stream completed without text."
                                    ) from None

                                yield AiStreamChunk(
                                    index=chunk_index,
                                    done=True,
                                    finish_reason=parse_finish_reason(
                                        payload.get("done_reason"),
                                        provider_name="Ollama",
                                    ),
                                )
                                return
            except (TimeoutError, httpx.TimeoutException):
                raise_timeout("Ollama")
            except httpx.RequestError as error:
                raise_request_error(
                    error,
                    provider_name="Ollama",
                )

            raise AiProtocolError(
                "Ollama stream ended before a terminal event."
            ) from None

        return generate()

    async def status(self) -> ProviderStatus:
        try:
            models = await fetch_ollama_models(
                self._http_client,
                base_url=self._base_url,
                total_timeout_seconds=self._total_timeout_seconds,
            )
        except AiAuthenticationError:
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.MISCONFIGURED,
                model=self._model,
                detail="Ollama rejected the status request.",
            )
        except (AiModelNotFoundError, AiResponseError):
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.MISCONFIGURED,
                model=self._model,
                detail="Ollama model listing endpoint is not available.",
            )
        except AiProviderError:
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.UNAVAILABLE,
                model=self._model,
                detail="Ollama service is not ready.",
            )

        if self._model not in models:
            return ProviderStatus(
                provider=self.name,
                state=ProviderState.MODEL_NOT_FOUND,
                model=self._model,
                detail="Ollama is reachable but the configured model is not registered.",
            )

        return ProviderStatus(
            provider=self.name,
            state=ProviderState.READY,
            model=self._model,
            detail="Ollama is reachable and the configured model is registered.",
        )
