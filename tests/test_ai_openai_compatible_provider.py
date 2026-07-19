import json
import unittest

import httpx
from pydantic import SecretStr

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
from app.ai.providers.openai_compatible import (
    OpenAiCompatibleProvider,
)

MODEL = "provider/model-1"
API_KEY = "private-test-api-key"


class OpenAiCompatibleProviderTests(
    unittest.IsolatedAsyncioTestCase,
):
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
                temperature=0.4,
                max_tokens=321,
            ),
        )

    def _provider(
        self,
        client: httpx.AsyncClient,
    ) -> OpenAiCompatibleProvider:
        return OpenAiCompatibleProvider(
            http_client=client,
            base_url="https://compatible.test/v1",
            api_key=SecretStr(API_KEY),
            model=MODEL,
            total_timeout_seconds=5.0,
        )

    async def test_complete_preserves_v1_path_headers_and_body(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                request.url.path,
                "/v1/chat/completions",
            )
            self.assertEqual(
                request.headers["Authorization"],
                f"Bearer {API_KEY}",
            )

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
            self.assertEqual(body["temperature"], 0.4)
            self.assertEqual(body["max_tokens"], 321)
            self.assertIs(body["stream"], False)

            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Compatible answer",
                            },
                            "finish_reason": "stop",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = self._provider(client)
            completion = await provider.complete(self.request)

            self.assertNotIn(API_KEY, repr(provider))

        self.assertEqual(completion.text, "Compatible answer")
        self.assertEqual(
            completion.finish_reason,
            AiFinishReason.STOP,
        )
        self.assertEqual(completion.provider, "openai_compatible")

    async def test_complete_rejects_invalid_protocol_payloads(self):
        invalid_responses = (
            httpx.Response(200, text="not-json"),
            httpx.Response(200, json={"choices": []}),
            httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                        }
                    ]
                },
            ),
            httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": "   "},
                            "finish_reason": "stop",
                        }
                    ]
                },
            ),
            httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": "answer"},
                            "finish_reason": "content_filter",
                        }
                    ]
                },
            ),
        )

        for response in invalid_responses:
            with self.subTest(content=response.content):
                transport = httpx.MockTransport(lambda _, current=response: current)

                async with httpx.AsyncClient(transport=transport) as client:
                    with self.assertRaises(AiProtocolError):
                        await self._provider(client).complete(self.request)

    async def test_stream_parses_sse_and_waits_for_done_marker(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.assertIs(body["stream"], True)

            return httpx.Response(
                200,
                text=(
                    ": keep-alive\n"
                    'data:{"choices":[{"delta":{"role":"assistant"},'
                    '"finish_reason":null}]}\n\n'
                    'data: {"choices":[{"delta":{"content":"你"},'
                    '"finish_reason":null}]}\n\n'
                    'data: {"choices":[{"delta":{"content":"好"},'
                    '"finish_reason":null}]}\n\n'
                    'data: {"choices":[{"delta":{},'
                    '"finish_reason":"stop"}]}\n\n'
                    "data:[DONE]\n\n"
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

    async def test_stream_rejects_missing_or_invalid_terminal_protocol(self):
        streams = (
            ('data: {"choices":[{"delta":{"content":"x"},"finish_reason":null}]}\n\n'),
            "data: [DONE]\n\n",
            "data: not-json\n\n",
            'data: {"choices":[]}\n\n',
            ('data: {"choices":[{"delta":{"content":123},"finish_reason":null}]}\n\n'),
            ('data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}\n\n'),
        )

        for stream_body in streams:
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

    async def test_http_and_network_failures_are_safe(self):
        mappings = (
            (401, AiAuthenticationError),
            (403, AiAuthenticationError),
            (404, AiModelNotFoundError),
            (408, AiTimeoutError),
            (429, AiRateLimitError),
            (503, AiUnavailableError),
        )

        for status_code, error_type in mappings:
            with self.subTest(status_code=status_code):
                transport = httpx.MockTransport(
                    lambda _, code=status_code: httpx.Response(
                        code,
                        text=f"private body {API_KEY}",
                    )
                )

                async with httpx.AsyncClient(transport=transport) as client:
                    with self.assertRaises(error_type) as raised:
                        await self._provider(client).complete(self.request)

                self.assertNotIn(API_KEY, str(raised.exception))
                self.assertNotIn("private body", str(raised.exception))

        def connection_handler(
            request: httpx.Request,
        ) -> httpx.Response:
            raise httpx.ConnectError(
                f"private failure {API_KEY}",
                request=request,
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(connection_handler)
        ) as client:
            with self.assertRaises(AiUnavailableError) as raised:
                await self._provider(client).complete(self.request)

        self.assertNotIn(API_KEY, str(raised.exception))

    async def test_status_encodes_model_and_maps_public_state(self):
        def ready_handler(request: httpx.Request) -> httpx.Response:
            self.assertIn(
                b"/v1/models/provider%2Fmodel-1",
                request.url.raw_path,
            )

            return httpx.Response(
                200,
                json={"id": MODEL},
            )

        scenarios = (
            (
                ready_handler,
                ProviderState.READY,
            ),
            (
                lambda _: httpx.Response(404),
                ProviderState.MODEL_NOT_FOUND,
            ),
            (
                lambda _: httpx.Response(401),
                ProviderState.MISCONFIGURED,
            ),
            (
                lambda _: httpx.Response(
                    200,
                    json={"id": "wrong-model"},
                ),
                ProviderState.UNAVAILABLE,
            ),
        )

        for handler, expected_state in scenarios:
            with self.subTest(expected_state=expected_state):
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(handler)
                ) as client:
                    status = await self._provider(client).status()

                self.assertEqual(status.state, expected_state)
                public_text = status.model_dump_json()
                self.assertNotIn(API_KEY, public_text)


if __name__ == "__main__":
    unittest.main()
