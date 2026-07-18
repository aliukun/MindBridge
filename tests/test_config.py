import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_default_settings(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            settings = Settings(_env_file=None)

        self.assertEqual(
            settings.app_name,
            "MindBridge Learn",
        )
        self.assertEqual(
            settings.app_version,
            "0.7.0",
        )
        self.assertEqual(
            settings.environment,
            "development",
        )
        self.assertEqual(
            settings.log_level,
            "INFO",
        )
        self.assertEqual(
            settings.server_port,
            8000,
        )
        self.assertEqual(
            settings.database_url,
            "sqlite:///./data/mindbridge.db",
        )
        self.assertEqual(
            settings.ai_provider,
            "mock",
        )
        self.assertEqual(
            settings.ai_temperature,
            0.0,
        )
        self.assertEqual(
            settings.ai_max_tokens,
            512,
        )
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
                "AI_PROVIDER": " MOCK ",
                "AI_TEMPERATURE": "0.5",
                "AI_MAX_TOKENS": "1024",
                "BOOTSTRAP_STUDENT_PASSWORD": ("student-password-2026"),
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)

        self.assertEqual(
            settings.app_name,
            "MindBridge Test",
        )
        self.assertEqual(
            settings.server_port,
            9090,
        )
        self.assertEqual(
            settings.database_url,
            "sqlite:///./data/test.db",
        )
        self.assertEqual(
            settings.log_level,
            "ERROR",
        )
        self.assertEqual(
            settings.ai_provider,
            "mock",
        )
        self.assertEqual(
            settings.ai_temperature,
            0.5,
        )
        self.assertEqual(
            settings.ai_max_tokens,
            1024,
        )
        self.assertIsNotNone(
            settings.bootstrap_student_password,
        )

        assert settings.bootstrap_student_password is not None

        self.assertEqual(
            settings.bootstrap_student_password.get_secret_value(),
            "student-password-2026",
        )

    def test_unknown_log_level_is_rejected(self):
        with patch.dict(
            os.environ,
            {
                "LOG_LEVEL": "VERBOSE",
            },
            clear=True,
        ):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None)

    def test_invalid_ai_numeric_configuration_is_rejected(
        self,
    ):
        invalid_environments = (
            {
                "AI_TEMPERATURE": "-0.1",
            },
            {
                "AI_TEMPERATURE": "2.1",
            },
            {
                "AI_TEMPERATURE": "NaN",
            },
            {
                "AI_MAX_TOKENS": "0",
            },
            {
                "AI_MAX_TOKENS": "4097",
            },
        )

        for environment in invalid_environments:
            with self.subTest(environment=environment):
                with patch.dict(
                    os.environ,
                    environment,
                    clear=True,
                ):
                    with self.assertRaises(ValidationError):
                        Settings(_env_file=None)

    def test_blank_ai_provider_is_rejected(self):
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "   ",
            },
            clear=True,
        ):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None)


if __name__ == "__main__":
    unittest.main()
