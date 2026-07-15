import os
import unittest
from unittest.mock import patch

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_default_settings(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            settings = Settings(
                _env_file=None
            )

        self.assertEqual(
            settings.app_name,
            "MindBridge Learn",
        )

        self.assertEqual(
            settings.app_version,
            "0.3.0",
        )

        self.assertEqual(
            settings.environment,
            "development",
        )

        self.assertEqual(
            settings.server_port,
            8000,
        )

        self.assertEqual(
            settings.database_url,
            "sqlite:///./data/mindbridge.db",
        )

        self.assertIsNone(
            settings.bootstrap_student_password
        )

        self.assertIsNone(
            settings.bootstrap_admin_password
        )

    def test_environment_variables_override_defaults(self):
        with patch.dict(
            os.environ,
            {
                "APP_NAME": "MindBridge Test",
                "SERVER_PORT": "9090",
                "DATABASE_URL": (
                    "sqlite:///./data/test.db"
                ),
                "BOOTSTRAP_STUDENT_PASSWORD": (
                    "student-password-2026"
                ),
            },
            clear=True,
        ):
            settings = Settings(
                _env_file=None
            )

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

        self.assertIsNotNone(
            settings.bootstrap_student_password
        )

        assert (
            settings.bootstrap_student_password
            is not None
        )

        self.assertEqual(
            settings
            .bootstrap_student_password
            .get_secret_value(),
            "student-password-2026",
        )


if __name__ == "__main__":
    unittest.main()