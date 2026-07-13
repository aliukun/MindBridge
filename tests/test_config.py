import os
import unittest
from unittest.mock import patch

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_default_settings(self):
        """未配置环境变量时，应使用代码默认值"""

        with patch.dict(os.environ, {}, clear = True):
            settings = Settings(_env_file = None)

        self.assertEqual(settings.app_name, "MindBridge Learn")
        self.assertEqual(settings.app_version, "0.1.0")
        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.server_port, 8000)

    def test_environment_variables_override_defaults(self):
        """系统环境变量应当能够覆盖默认配置。"""

        with patch.dict(
            os.environ,
            {
                "APP_NAME": "MindBridge Test",
                "SERVER_PORT": "9090",
            },
            clear=True,
        ):
            settings = Settings(_env_file = None)

        self.assertEqual(settings.app_name, "MindBridge Test")
        self.assertEqual(settings.server_port, 9090)

if __name__ == "__main__":
    unittest.main()