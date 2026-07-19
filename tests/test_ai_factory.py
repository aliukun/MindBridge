import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.ai.contracts import AiRequestOptions
from app.ai.errors import AiConfigurationError
from app.ai.factory import (
    build_ai_provider,
    build_ai_request_options,
    validate_ai_provider_settings,
)
from app.ai.providers.base import AiProvider
from app.ai.providers.mock import DeterministicMockProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import (
    OpenAiCompatibleProvider,
)
from app.core.config import Settings
from app.main import create_app


class AiFactoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_factory_builds_all_explicit_provider_types(self):
        settings_and_types = (
            (
                Settings(
                    ai_provider="mock",
                    _env_file=None,
                ),
                DeterministicMockProvider,
            ),
            (
                Settings(
                    ai_provider="ollama",
                    _env_file=None,
                ),
                OllamaProvider,
            ),
            (
                Settings(
                    ai_provider="openai_compatible",
                    openai_compatible_base_url=("https://compatible.test/v1"),
                    openai_compatible_api_key="private-key",
                    openai_compatible_model="model-1",
                    _env_file=None,
                ),
                OpenAiCompatibleProvider,
            ),
        )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200))
        ) as http_client:
            for settings, provider_type in settings_and_types:
                with self.subTest(provider=settings.ai_provider):
                    provider = build_ai_provider(
                        settings,
                        http_client=http_client,
                    )

                    self.assertIsInstance(provider, provider_type)
                    self.assertIsInstance(provider, AiProvider)

                    if isinstance(
                        provider,
                        (OllamaProvider, OpenAiCompatibleProvider),
                    ):
                        self.assertIs(
                            provider._http_client,
                            http_client,
                        )

    def test_unknown_provider_never_falls_back_to_mock(self):
        settings = Settings.model_construct(ai_provider="provider-typo")

        with self.assertRaises(AiConfigurationError):
            validate_ai_provider_settings(settings)

        with self.assertRaises(AiConfigurationError):
            create_app(settings=settings)

    def test_incomplete_compatible_configuration_is_rejected_again(self):
        settings = Settings.model_construct(
            ai_provider="openai_compatible",
            openai_compatible_base_url=None,
            openai_compatible_api_key=None,
            openai_compatible_model=None,
        )

        with self.assertRaises(AiConfigurationError):
            validate_ai_provider_settings(settings)

    def test_settings_build_immutable_request_options(self):
        settings = Settings(
            ai_temperature=0.4,
            ai_max_tokens=1024,
            _env_file=None,
        )

        options = build_ai_request_options(settings)

        self.assertEqual(
            options,
            AiRequestOptions(
                temperature=0.4,
                max_tokens=1024,
            ),
        )


class AiLifecycleTests(unittest.TestCase):
    def test_lifespan_creates_reuses_and_closes_shared_client(self):
        network_calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal network_calls
            network_calls += 1

            return httpx.Response(200)

        settings = Settings(
            ai_provider="ollama",
            ai_temperature=0.2,
            ai_max_tokens=256,
            _env_file=None,
        )
        application = create_app(
            settings=settings,
            http_transport=httpx.MockTransport(handler),
        )

        self.assertEqual(
            application.state.ai_request_options,
            AiRequestOptions(
                temperature=0.2,
                max_tokens=256,
            ),
        )
        self.assertIs(application.state.settings, settings)

        with patch("app.main.bootstrap_database") as bootstrap:
            with TestClient(application):
                http_client = application.state.http_client
                provider = application.state.ai_provider

                self.assertFalse(http_client.is_closed)
                self.assertIsInstance(provider, OllamaProvider)
                self.assertIs(
                    provider._http_client,
                    http_client,
                )

        bootstrap.assert_called_once_with()
        self.assertTrue(http_client.is_closed)
        self.assertEqual(network_calls, 0)

    def test_mock_startup_also_does_not_access_network(self):
        def reject_network(_: httpx.Request) -> httpx.Response:
            raise AssertionError(
                "Application startup must not access an external service."
            )

        application = create_app(
            settings=Settings(_env_file=None),
            http_transport=httpx.MockTransport(reject_network),
        )

        with patch("app.main.bootstrap_database"):
            with TestClient(application):
                self.assertIsInstance(
                    application.state.ai_provider,
                    DeterministicMockProvider,
                )


if __name__ == "__main__":
    unittest.main()
