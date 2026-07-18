import unittest
from unittest.mock import patch

from app.ai.contracts import (
    AiFinishReason,
    AiMessage,
    AiRequest,
    AiRequestOptions,
    ProviderState,
)
from app.ai.errors import AiConfigurationError
from app.ai.providers.mock import (
    MOCK_MODEL_NAME,
    DeterministicMockProvider,
)


class MockAiProviderTests(
    unittest.IsolatedAsyncioTestCase,
):
    def setUp(self):
        self.request = AiRequest(
            messages=(
                AiMessage(
                    role="system",
                    content="You are a test assistant.",
                ),
                AiMessage(
                    role="user",
                    content="Hello",
                ),
            ),
            options=AiRequestOptions(
                temperature=0.0,
                max_tokens=128,
            ),
        )

    async def test_same_request_is_deterministic_across_instances(
        self,
    ):
        first_provider = DeterministicMockProvider()
        second_provider = DeterministicMockProvider()

        first = await first_provider.complete(
            self.request,
        )
        second = await first_provider.complete(
            self.request,
        )
        third = await second_provider.complete(
            self.request,
        )

        self.assertEqual(first, second)
        self.assertEqual(first, third)
        self.assertEqual(first.provider, "mock")
        self.assertEqual(
            first.model,
            MOCK_MODEL_NAME,
        )
        self.assertEqual(
            first.finish_reason,
            AiFinishReason.STOP,
        )

    async def test_different_request_changes_fingerprint(
        self,
    ):
        provider = DeterministicMockProvider()

        different_request = AiRequest(
            messages=(
                AiMessage(
                    role="user",
                    content="Different input",
                ),
            )
        )

        first = await provider.complete(
            self.request,
        )
        second = await provider.complete(
            different_request,
        )

        self.assertNotEqual(
            first.text,
            second.text,
        )

    async def test_stream_rebuilds_completion_and_finishes_once(
        self,
    ):
        provider = DeterministicMockProvider(
            chunk_size=5,
        )

        completion = await provider.complete(
            self.request,
        )
        chunks = [
            chunk
            async for chunk in provider.stream(
                self.request,
            )
        ]

        self.assertEqual(
            [chunk.index for chunk in chunks],
            list(range(len(chunks))),
        )
        self.assertEqual(
            sum(chunk.done for chunk in chunks),
            1,
        )
        self.assertTrue(chunks[-1].done)
        self.assertEqual(
            chunks[-1].delta,
            "",
        )
        self.assertEqual(
            chunks[-1].finish_reason,
            completion.finish_reason,
        )
        self.assertTrue(
            all(not chunk.done and chunk.finish_reason is None for chunk in chunks[:-1])
        )
        self.assertEqual(
            "".join(chunk.delta for chunk in chunks),
            completion.text,
        )

    async def test_status_is_ready_without_network(
        self,
    ):
        provider = DeterministicMockProvider()

        status = await provider.status()

        self.assertEqual(
            status.provider,
            "mock",
        )
        self.assertEqual(
            status.state,
            ProviderState.READY,
        )
        self.assertEqual(
            status.model,
            MOCK_MODEL_NAME,
        )

    async def test_complete_stream_and_status_do_not_use_network(
        self,
    ):
        provider = DeterministicMockProvider()

        with patch(
            "socket.create_connection",
            side_effect=AssertionError("Mock Provider must not access the network."),
        ) as create_connection:
            await provider.complete(
                self.request,
            )

            _ = [
                chunk
                async for chunk in provider.stream(
                    self.request,
                )
            ]

            await provider.status()

        create_connection.assert_not_called()

    def test_invalid_mock_configuration_is_rejected(
        self,
    ):
        with self.assertRaises(
            AiConfigurationError,
        ):
            DeterministicMockProvider(
                model="   ",
            )

        invalid_chunk_sizes = (
            0,
            -1,
            True,
        )

        for chunk_size in invalid_chunk_sizes:
            with self.subTest(chunk_size=chunk_size):
                with self.assertRaises(
                    AiConfigurationError,
                ):
                    DeterministicMockProvider(
                        chunk_size=chunk_size,
                    )


if __name__ == "__main__":
    unittest.main()
