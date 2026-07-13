import unittest

from fastapi.testclient import TestClient

from app.main import app


class HealthEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_returns_up(self):
        response = self.client.get("/actuator/health")

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["status"], "UP")
        self.assertEqual(body["name"], "MindBridge Learn")
        self.assertEqual(body["version"], "0.1.0")
        self.assertEqual(body["environment"], "development")

    def test_unknown_path_returns_not_found(self):
        response = self.client.get("/not-found")

        self.assertEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
