import hashlib
import json
from collections.abc import AsyncIterator

from app.ai.contracts import (
    AiCompletion,
    AiFinishReason,
    AiRequest,
    AiStreamChunk,
    ProviderState,
    ProviderStatus,
)
from app.ai.errors import AiConfigurationError

MOCK_PROVIDER_NAME = "mock"
MOCK_MODEL_NAME = "mindbridge-mock-v1"


class DeterministicMockProvider:
    """不访问网络且跨进程结果稳定的 Mock Provider。"""

    def __init__(
        self,
        *,
        model: str = MOCK_MODEL_NAME,
        chunk_size: int = 8,
    ) -> None:
        normalized_model = model.strip()

        if not normalized_model:
            raise AiConfigurationError("Mock model name must not be blank.")

        if isinstance(chunk_size, bool) or chunk_size < 1:
            raise AiConfigurationError("Mock chunk size must be a positive integer.")

        self._model = normalized_model
        self._chunk_size = chunk_size

    @property
    def name(self) -> str:
        return MOCK_PROVIDER_NAME

    @property
    def model(self) -> str:
        return self._model

    def _request_fingerprint(
        self,
        request: AiRequest,
    ) -> str:
        payload = {
            "model": self._model,
            "request": request.model_dump(
                mode="json",
            ),
        }

        canonical_json = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]

    async def complete(
        self,
        request: AiRequest,
    ) -> AiCompletion:
        fingerprint = self._request_fingerprint(
            request,
        )

        return AiCompletion(
            text=f"Mock completion [{fingerprint}]",
            provider=self.name,
            model=self._model,
            finish_reason=AiFinishReason.STOP,
        )

    def stream(
        self,
        request: AiRequest,
    ) -> AsyncIterator[AiStreamChunk]:
        async def generate() -> AsyncIterator[AiStreamChunk]:
            completion = await self.complete(
                request,
            )

            chunk_index = 0

            for start in range(
                0,
                len(completion.text),
                self._chunk_size,
            ):
                yield AiStreamChunk(
                    index=chunk_index,
                    delta=completion.text[start : start + self._chunk_size],
                )

                chunk_index += 1

            yield AiStreamChunk(
                index=chunk_index,
                done=True,
                finish_reason=completion.finish_reason,
            )

        return generate()

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider=self.name,
            state=ProviderState.READY,
            model=self._model,
            detail=("Deterministic offline Mock Provider is ready."),
        )
