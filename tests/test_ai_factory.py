import unittest
from unittest.mock import patch

from app.ai.contracts import AiRequestOptions
from app.ai.errors import AiConfigurationError
from app.ai.factory import (
    build_ai_provider,
    build_ai_request_options,
)
from app.ai.providers.base import AiProvider
from app.ai.providers.mock import (
    DeterministicMockProvider,
)
from app.core.config import Settings
from app.main import create_app


class AiFactoryTests(unittest.TestCase):
    def test_mock_names_build_mock_provider(self):
        provider_names = (
            "mock",
            " MOCK ",
        )

        for provider_name in provider_names:
            with self.subTest(
                provider_name=provider_name,
            ):
                provider = build_ai_provider(
                    provider_name,
                )

                self.assertIsInstance(
                    provider,
                    DeterministicMockProvider,
                )
                self.assertIsInstance(
                    provider,
                    AiProvider,
                )

    def test_unknown_or_blank_provider_is_rejected(self):
        provider_names = (
            "unknown",
            "",
            "   ",
        )

        for provider_name in provider_names:
            with self.subTest(
                provider_name=provider_name,
            ):
                with self.assertRaises(
                    AiConfigurationError,
                ):
                    build_ai_provider(
                        provider_name,
                    )

    def test_settings_build_immutable_request_options(
        self,
    ):
        settings = Settings(
            ai_temperature=0.4,
            ai_max_tokens=1024,
            _env_file=None,
        )

        options = build_ai_request_options(
            settings,
        )

        self.assertEqual(
            options,
            AiRequestOptions(
                temperature=0.4,
                max_tokens=1024,
            ),
        )

    def test_create_app_stores_provider_and_options(
        self,
    ):
        settings = Settings(
            ai_provider="mock",
            ai_temperature=0.2,
            ai_max_tokens=256,
            _env_file=None,
        )

        with patch(
            "app.main.get_settings",
            return_value=settings,
        ):
            application = create_app()

        self.assertIsInstance(
            application.state.ai_provider,
            DeterministicMockProvider,
        )
        self.assertEqual(
            application.state.ai_request_options,
            AiRequestOptions(
                temperature=0.2,
                max_tokens=256,
            ),
        )

    def test_create_app_fails_for_unknown_provider(
        self,
    ):
        settings = Settings(
            ai_provider="provider-typo",
            _env_file=None,
        )

        with patch(
            "app.main.get_settings",
            return_value=settings,
        ):
            with self.assertRaises(
                AiConfigurationError,
            ):
                create_app()


if __name__ == "__main__":
    unittest.main()
