import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


class HealthEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_health_returns_up(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)

        with patch(
            "app.api.routes.get_settings",
            return_value=settings,
        ):
            response = self.client.get("/actuator/health")

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["status"], "UP")
        self.assertEqual(body["name"], "MindBridge Learn")
        self.assertEqual(body["version"], "0.2.0")
        self.assertEqual(body["environment"], "development")

    def test_unknown_path_returns_not_found(self):
        response = self.client.get("/not-found")

        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
