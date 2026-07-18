from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.ai.contracts import (
    AiCompletion,
    AiRequest,
    AiStreamChunk,
    ProviderStatus,
)


@runtime_checkable
class AiProvider(Protocol):
    """所有 AI Provider 必须满足的结构化接口。"""

    @property
    def name(self) -> str:
        """返回稳定的 Provider 名称。"""

        ...

    async def complete(
        self,
        request: AiRequest,
    ) -> AiCompletion:
        """返回一次完整生成结果。"""

        ...

    def stream(
        self,
        request: AiRequest,
    ) -> AsyncIterator[AiStreamChunk]:
        """返回可以直接 async for 的流式结果。"""

        ...

    async def status(self) -> ProviderStatus:
        """返回不包含秘密的 Provider 状态。"""

        ...
