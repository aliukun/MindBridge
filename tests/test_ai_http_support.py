import unittest

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
from app.ai.providers.http_support import (
    build_http_timeout,
    iter_sse_data,
    join_provider_url,
    parse_finish_reason,
    raise_for_provider_status,
    raise_request_error,
    response_json_object,
)
from app.core.config import Settings


class HttpSupportTests(unittest.TestCase):
    def test_builds_phase_timeouts_and_preserves_base_path(self):
        settings = Settings(
            ai_connect_timeout_seconds=3.0,
            ai_read_timeout_seconds=20.0,
            _env_file=None,
        )

        timeout = build_http_timeout(settings)

        self.assertEqual(timeout.connect, 3.0)
        self.assertEqual(timeout.pool, 3.0)
        self.assertEqual(timeout.read, 20.0)
        self.assertEqual(timeout.write, 20.0)
        self.assertEqual(
            join_provider_url(
                "https://example.test/v1/",
                "/chat/completions",
            ),
            "https://example.test/v1/chat/completions",
        )

    def test_http_statuses_map_to_stable_errors(self):
        mappings = (
            (401, AiAuthenticationError),
            (403, AiAuthenticationError),
            (404, AiModelNotFoundError),
            (408, AiTimeoutError),
            (429, AiRateLimitError),
            (500, AiUnavailableError),
            (503, AiUnavailableError),
            (400, AiResponseError),
            (302, AiResponseError),
        )

        for status_code, error_type in mappings:
            with self.subTest(status_code=status_code):
                response = httpx.Response(
                    status_code,
                    text="secret provider body",
                )

                with self.assertRaises(error_type) as raised:
                    raise_for_provider_status(
                        response,
                        provider_name="test-provider",
                    )

                self.assertNotIn(
                    "secret provider body",
                    str(raised.exception),
                )

        raise_for_provider_status(
            httpx.Response(204),
            provider_name="test-provider",
        )

    def test_listing_endpoint_404_is_not_called_model_missing(self):
        with self.assertRaises(AiResponseError):
            raise_for_provider_status(
                httpx.Response(404),
                provider_name="test-provider",
                not_found_is_model=False,
            )

    def test_network_errors_are_safely_classified(self):
        request = httpx.Request(
            "GET",
            "https://example.test",
        )
        mappings = (
            (
                httpx.ReadTimeout(
                    "secret timeout detail",
                    request=request,
                ),
                AiTimeoutError,
            ),
            (
                httpx.ConnectError(
                    "secret connection detail",
                    request=request,
                ),
                AiUnavailableError,
            ),
            (
                httpx.RemoteProtocolError(
                    "secret protocol detail",
                    request=request,
                ),
                AiProtocolError,
            ),
        )

        for error, error_type in mappings:
            with self.subTest(error_type=error_type.__name__):
                with self.assertRaises(error_type) as raised:
                    raise_request_error(
                        error,
                        provider_name="test-provider",
                    )

                self.assertNotIn(
                    "secret",
                    str(raised.exception),
                )

    def test_json_object_and_finish_reason_are_strict(self):
        payload = response_json_object(
            httpx.Response(
                200,
                json={"ok": True},
            ),
            provider_name="test-provider",
        )

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(
            parse_finish_reason(
                "stop",
                provider_name="test-provider",
            ),
            AiFinishReason.STOP,
        )
        self.assertEqual(
            parse_finish_reason(
                "length",
                provider_name="test-provider",
            ),
            AiFinishReason.LENGTH,
        )

        invalid_responses = (
            httpx.Response(200, text="not-json"),
            httpx.Response(200, json=[]),
        )

        for response in invalid_responses:
            with self.subTest(content=response.content):
                with self.assertRaises(AiProtocolError):
                    response_json_object(
                        response,
                        provider_name="test-provider",
                    )

        for reason in (None, "content_filter", "tool_calls"):
            with self.subTest(reason=reason):
                with self.assertRaises(AiProtocolError):
                    parse_finish_reason(
                        reason,
                        provider_name="test-provider",
                    )


class SseParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_sse_parser_accepts_spacing_comments_and_eof(self):
        response = httpx.Response(
            200,
            text=(
                ": keep-alive\n"
                "event: message\n"
                'data:{"first":1}\n\n'
                "data: first line\n"
                "data:second line\n\n"
                "data: [DONE]"
            ),
        )

        events = [
            event
            async for event in iter_sse_data(
                response,
            )
        ]

        self.assertEqual(
            events,
            [
                '{"first":1}',
                "first line\nsecond line",
                "[DONE]",
            ],
        )


if __name__ == "__main__":
    unittest.main()
