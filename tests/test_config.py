import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import SecretStr, ValidationError

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_default_settings(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            settings = Settings(_env_file=None)

        self.assertEqual(settings.app_name, "MindBridge Learn")
        self.assertEqual(settings.app_version, "0.8.0")
        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.server_port, 8000)
        self.assertEqual(
            settings.database_url,
            "sqlite:///./data/mindbridge.db",
        )
        self.assertEqual(settings.ai_provider, "mock")
        self.assertEqual(settings.ai_temperature, 0.0)
        self.assertEqual(settings.ai_max_tokens, 512)
        self.assertEqual(
            settings.ai_connect_timeout_seconds,
            5.0,
        )
        self.assertEqual(
            settings.ai_read_timeout_seconds,
            60.0,
        )
        self.assertEqual(
            settings.ai_total_timeout_seconds,
            120.0,
        )
        self.assertEqual(
            settings.ollama_base_url,
            "http://127.0.0.1:11434",
        )
        self.assertEqual(
            settings.ollama_model,
            "mindbridge-qwen2.5-7b-ft:latest",
        )
        self.assertEqual(
            settings.finetuned_model_dir,
            Path("models/mindbridge-qwen2.5-7b-ft"),
        )
        self.assertIsNone(settings.openai_compatible_api_key)
        self.assertIsNone(settings.bootstrap_student_password)
        self.assertIsNone(settings.bootstrap_admin_password)

    def test_environment_variables_override_defaults(self):
        with patch.dict(
            os.environ,
            {
                "APP_NAME": "MindBridge Test",
                "SERVER_PORT": "9090",
                "DATABASE_URL": "sqlite:///./data/test.db",
                "LOG_LEVEL": "ERROR",
                "AI_PROVIDER": " OLLAMA ",
                "AI_TEMPERATURE": "0.5",
                "AI_MAX_TOKENS": "1024",
                "AI_CONNECT_TIMEOUT_SECONDS": "2.5",
                "AI_READ_TIMEOUT_SECONDS": "30",
                "AI_TOTAL_TIMEOUT_SECONDS": "45",
                "OLLAMA_BASE_URL": "http://localhost:11434/",
                "OLLAMA_MODEL": " local-model:latest ",
                "BOOTSTRAP_STUDENT_PASSWORD": ("student-password-2026"),
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)

        self.assertEqual(settings.app_name, "MindBridge Test")
        self.assertEqual(settings.server_port, 9090)
        self.assertEqual(settings.log_level, "ERROR")
        self.assertEqual(settings.ai_provider, "ollama")
        self.assertEqual(settings.ai_temperature, 0.5)
        self.assertEqual(settings.ai_max_tokens, 1024)
        self.assertEqual(
            settings.ai_connect_timeout_seconds,
            2.5,
        )
        self.assertEqual(settings.ollama_model, "local-model:latest")
        self.assertEqual(
            settings.ollama_base_url,
            "http://localhost:11434",
        )
        self.assertIsNotNone(settings.bootstrap_student_password)

    def test_openai_compatible_requires_all_private_configuration(self):
        missing_payloads = (
            {},
            {
                "openai_compatible_base_url": ("https://compatible.test/v1"),
            },
            {
                "openai_compatible_base_url": ("https://compatible.test/v1"),
                "openai_compatible_model": "model-1",
            },
            {
                "openai_compatible_base_url": ("https://compatible.test/v1"),
                "openai_compatible_model": "model-1",
                "openai_compatible_api_key": "   ",
            },
        )

        for payload in missing_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    Settings(
                        ai_provider="openai_compatible",
                        _env_file=None,
                        **payload,
                    )

        settings = Settings(
            ai_provider="openai_compatible",
            openai_compatible_base_url=("https://compatible.test/v1/"),
            openai_compatible_model=" model-1 ",
            openai_compatible_api_key="private-key",
            _env_file=None,
        )

        self.assertEqual(
            settings.openai_compatible_base_url,
            "https://compatible.test/v1",
        )
        self.assertEqual(
            settings.openai_compatible_model,
            "model-1",
        )
        self.assertIsInstance(
            settings.openai_compatible_api_key,
            SecretStr,
        )
        self.assertNotIn("private-key", repr(settings))

    def test_unknown_or_blank_provider_is_rejected(self):
        for provider in ("unknown", "", "   "):
            with self.subTest(provider=provider):
                with self.assertRaises(ValidationError):
                    Settings(
                        ai_provider=provider,
                        _env_file=None,
                    )

    def test_invalid_http_base_urls_are_rejected(self):
        invalid_urls = (
            "ftp://example.test",
            "http:///missing-host",
            "https://user:password@example.test/v1",
            "https://example.test/v1?secret=value",
            "https://example.test/v1#fragment",
            "https://example test/v1",
        )

        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    Settings(
                        ollama_base_url=url,
                        _env_file=None,
                    )

    def test_invalid_ai_numeric_configuration_is_rejected(self):
        invalid_payloads = (
            {"ai_temperature": -0.1},
            {"ai_temperature": 2.1},
            {"ai_temperature": float("nan")},
            {"ai_max_tokens": 0},
            {"ai_max_tokens": 4097},
            {"ai_connect_timeout_seconds": 0},
            {"ai_read_timeout_seconds": -1},
            {"ai_total_timeout_seconds": float("inf")},
            {"ai_total_timeout_seconds": 601},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    Settings(
                        _env_file=None,
                        **payload,
                    )

    def test_model_assets_must_stay_inside_project_models(self):
        invalid_payloads = (
            {"finetuned_model_dir": "../outside"},
            {"finetuned_model_dir": "data/model"},
            {"finetuned_model_file": "nested/model.gguf"},
            {"finetuned_model_file": "model.bin"},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    Settings(
                        _env_file=None,
                        **payload,
                    )

    def test_unknown_log_level_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(
                log_level="VERBOSE",
                _env_file=None,
            )


if __name__ == "__main__":
    unittest.main()
