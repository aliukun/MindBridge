from collections.abc import AsyncIterator, Callable

from app.ai.contracts import (
    AiCompletion,
    AiFinishReason,
    AiRequest,
    AiStreamChunk,
    ProviderState,
    ProviderStatus,
)


class ScriptedAiProvider:
    """按队列返回文本或抛异常；完全不访问网络。"""

    def __init__(
        self,
        *steps: str | Exception,
        on_complete: Callable[[AiRequest], None] | None = None,
    ) -> None:
        self._steps = list(steps)
        self._on_complete = on_complete
        self.requests: list[AiRequest] = []

    @property
    def name(self) -> str:
        return "scripted"

    def queue(self, *steps: str | Exception) -> None:
        self._steps.extend(steps)

    async def complete(self, request: AiRequest) -> AiCompletion:
        self.requests.append(request)

        if self._on_complete is not None:
            self._on_complete(request)

        if not self._steps:
            raise AssertionError("Unexpected AI completion call.")

        step = self._steps.pop(0)

        if isinstance(step, Exception):
            raise step

        return AiCompletion(
            text=step,
            provider=self.name,
            model="scripted-model",
            finish_reason=AiFinishReason.STOP,
        )

    def stream(self, request: AiRequest) -> AsyncIterator[AiStreamChunk]:
        async def generate() -> AsyncIterator[AiStreamChunk]:
            completion = await self.complete(request)

            yield AiStreamChunk(
                index=0,
                delta=completion.text,
            )
            yield AiStreamChunk(
                index=1,
                done=True,
                finish_reason=completion.finish_reason,
            )

        return generate()

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider=self.name,
            state=ProviderState.READY,
            model="scripted-model",
        )
