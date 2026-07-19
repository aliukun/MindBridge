import json
import unittest

import httpx

from app.ai.contracts import (
    AiFinishReason,
    AiMessage,
    AiRequest,
    AiRequestOptions,
    ProviderState,
)
from app.ai.errors import (
    AiAuthenticationError,
    AiModelNotFoundError,
    AiProtocolError,
    AiRateLimitError,
    AiTimeoutError,
    AiUnavailableError,
)
from app.ai.providers.ollama import OllamaProvider

MODEL = "mindbridge-test:latest"


class OllamaProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = AiRequest(
            messages=(
                AiMessage(
                    role="system",
                    content="System instruction",
                ),
                AiMessage(
                    role="user",
                    content="Hello",
                ),
            ),
            options=AiRequestOptions(
                temperature=0.25,
                max_tokens=123,
            ),
        )

    def _provider(
        self,
        client: httpx.AsyncClient,
    ) -> OllamaProvider:
        return OllamaProvider(
            http_client=client,
            base_url="http://ollama.test",
            model=MODEL,
            total_timeout_seconds=5.0,
        )

    async def test_complete_sends_ollama_shape_and_parses_result(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/api/chat")

            body = json.loads(request.content)

            self.assertEqual(body["model"], MODEL)
            self.assertEqual(
                body["messages"],
                [
                    {
                        "role": "system",
                        "content": "System instruction",
                    },
                    {
                        "role": "user",
                        "content": "Hello",
                    },
                ],
            )
            self.assertIs(body["stream"], False)
            self.assertEqual(
                body["options"],
                {
                    "temperature": 0.25,
                    "num_predict": 123,
                },
            )

            return httpx.Response(
                200,
                json={
                    "message": {
                        "role": "assistant",
                        "content": "Local answer",
                    },
                    "done": True,
                    "done_reason": "stop",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            completion = await self._provider(client).complete(self.request)

        self.assertEqual(completion.text, "Local answer")
        self.assertEqual(completion.provider, "ollama")
        self.assertEqual(completion.model, MODEL)
        self.assertEqual(
            completion.finish_reason,
            AiFinishReason.STOP,
        )

    async def test_complete_maps_length_finish_reason(self):
        transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "message": {"content": "Truncated"},
                    "done": True,
                    "done_reason": "length",
                },
            )
        )

        async with httpx.AsyncClient(transport=transport) as client:
            completion = await self._provider(client).complete(self.request)

        self.assertEqual(
            completion.finish_reason,
            AiFinishReason.LENGTH,
        )

    async def test_complete_rejects_invalid_protocol_payloads(self):
        invalid_responses = (
            httpx.Response(200, text="not-json"),
            httpx.Response(
                200,
                json={
                    "message": {"content": "answer"},
                    "done": False,
                    "done_reason": "stop",
                },
            ),
            httpx.Response(
                200,
                json={
                    "done": True,
                    "done_reason": "stop",
                },
            ),
            httpx.Response(
                200,
                json={
                    "message": {"content": "   "},
                    "done": True,
                    "done_reason": "stop",
                },
            ),
            httpx.Response(
                200,
                json={
                    "message": {"content": "answer"},
                    "done": True,
                    "done_reason": "unknown",
                },
            ),
        )

        for response in invalid_responses:
            with self.subTest(content=response.content):
                transport = httpx.MockTransport(lambda _, current=response: current)

                async with httpx.AsyncClient(transport=transport) as client:
                    with self.assertRaises(AiProtocolError):
                        await self._provider(client).complete(self.request)

    async def test_stream_parses_ndjson_and_emits_one_terminal_chunk(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.assertIs(body["stream"], True)

            return httpx.Response(
                200,
                text=(
                    '{"message":{"content":"你"},"done":false}\n'
                    "\n"
                    '{"message":{"content":"好"},"done":true,'
                    '"done_reason":"stop"}\n'
                ),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            chunks = [
                chunk async for chunk in self._provider(client).stream(self.request)
            ]

        self.assertEqual(
            [chunk.index for chunk in chunks],
            [0, 1, 2],
        )
        self.assertEqual(
            "".join(chunk.delta for chunk in chunks),
            "你好",
        )
        self.assertEqual(sum(chunk.done for chunk in chunks), 1)
        self.assertTrue(chunks[-1].done)
        self.assertEqual(
            chunks[-1].finish_reason,
            AiFinishReason.STOP,
        )

    async def test_stream_rejects_bad_or_unfinished_ndjson(self):
        invalid_streams = (
            '{"message":{"content":"partial"},"done":false}\n',
            "not-json\n",
            '{"message":{"content":"x"}}\n',
            ('{"message":{"content":"x"},"done":false,"done_reason":"stop"}\n'),
            ('{"message":{"content":""},"done":true,"done_reason":"stop"}\n'),
        )

        for stream_body in invalid_streams:
            with self.subTest(stream_body=stream_body):
                transport = httpx.MockTransport(
                    lambda _, body=stream_body: httpx.Response(
                        200,
                        text=body,
                    )
                )

                async with httpx.AsyncClient(transport=transport) as client:
                    with self.assertRaises(AiProtocolError):
                        _ = [
                            chunk
                            async for chunk in self._provider(client).stream(
                                self.request
                            )
                        ]

    async def test_http_and_network_failures_use_stable_exceptions(self):
        status_mappings = (
            (401, AiAuthenticationError),
            (404, AiModelNotFoundError),
            (408, AiTimeoutError),
            (429, AiRateLimitError),
            (503, AiUnavailableError),
        )

        for status_code, error_type in status_mappings:
            with self.subTest(status_code=status_code):
                transport = httpx.MockTransport(
                    lambda _, code=status_code: httpx.Response(
                        code,
                        text="private provider body",
                    )
                )

                async with httpx.AsyncClient(transport=transport) as client:
                    with self.assertRaises(error_type) as raised:
                        await self._provider(client).complete(self.request)

                self.assertNotIn(
                    "private provider body",
                    str(raised.exception),
                )

        def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout(
                "private timeout detail",
                request=request,
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(timeout_handler)
        ) as client:
            with self.assertRaises(AiTimeoutError):
                await self._provider(client).complete(self.request)

    async def test_status_distinguishes_ready_missing_and_unavailable(self):
        scenarios = (
            (
                httpx.Response(
                    200,
                    json={"models": [{"name": MODEL}]},
                ),
                ProviderState.READY,
            ),
            (
                httpx.Response(
                    200,
                    json={"models": [{"name": "other:latest"}]},
                ),
                ProviderState.MODEL_NOT_FOUND,
            ),
            (
                httpx.Response(200, json={"models": "bad"}),
                ProviderState.UNAVAILABLE,
            ),
            (
                httpx.Response(401),
                ProviderState.MISCONFIGURED,
            ),
        )

        for response, expected_state in scenarios:
            with self.subTest(expected_state=expected_state):
                transport = httpx.MockTransport(lambda _, current=response: current)

                async with httpx.AsyncClient(transport=transport) as client:
                    result = await self._provider(client).status()

                self.assertEqual(result.state, expected_state)
                self.assertNotIn("private", result.detail or "")


if __name__ == "__main__":
    unittest.main()
