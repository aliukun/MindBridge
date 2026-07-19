import tempfile
import unittest
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.bootstrap import create_schema
from app.core.config import PROJECT_ROOT, Settings
from app.core.database import Base, build_engine, get_db
from app.main import create_app
from app.models.entities import ROLE_ADMIN, ROLE_USER
from app.services.user_service import create_user


class AiStatusApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite+pysqlite:///:memory:")
        create_schema(self.engine)
        self.SessionTesting = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

        with self.SessionTesting() as database:
            create_user(
                database,
                username="student",
                display_name="Test Student",
                password="student-password-2026",
                roles={ROLE_USER},
            )
            create_user(
                database,
                username="admin",
                display_name="Test Admin",
                password="admin-password-2026",
                roles={ROLE_USER, ROLE_ADMIN},
            )
            database.commit()

        models_root = PROJECT_ROOT / "models"
        models_root.mkdir(exist_ok=True)
        self.temporary_model_directory = tempfile.TemporaryDirectory(dir=models_root)
        model_relative_directory = Path(
            self.temporary_model_directory.name
        ).relative_to(PROJECT_ROOT)

        self.api_key = "must-never-appear-in-status"
        self.requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)

            if request.url.path == "/api/tags":
                return httpx.Response(
                    200,
                    json={"models": [{"name": ("test-model:latest")}]},
                )

            if request.url.path == "/api/chat":
                return httpx.Response(
                    200,
                    json={
                        "message": {"content": "READY"},
                        "done": True,
                        "done_reason": "stop",
                    },
                )

            raise AssertionError("Unexpected test URL")

        settings = Settings(
            ai_provider="mock",
            ollama_base_url="http://ollama.test",
            ollama_model="test-model:latest",
            finetuned_model_dir=model_relative_directory,
            finetuned_model_file="test-model.gguf",
            openai_compatible_api_key=self.api_key,
            _env_file=None,
        )
        self.application = create_app(
            settings=settings,
            http_transport=httpx.MockTransport(handler),
        )

        def override_get_db() -> Generator[Session, None, None]:
            database = self.SessionTesting()

            try:
                yield database
            finally:
                database.close()

        self.application.dependency_overrides[get_db] = override_get_db
        self.bootstrap_patcher = patch("app.main.bootstrap_database")
        self.bootstrap_patcher.start()
        self.client_context = TestClient(self.application)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.bootstrap_patcher.stop()
        self.application.dependency_overrides.clear()
        self.temporary_model_directory.cleanup()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_status_requires_admin_authentication(self):
        anonymous = self.client.get("/api/admin/ai/status")
        student = self.client.get(
            "/api/admin/ai/status",
            auth=(
                "student",
                "student-password-2026",
            ),
        )

        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(student.status_code, 403)
        self.assertEqual(self.requests, [])

    def test_admin_receives_four_layers_without_secrets_or_paths(self):
        response = self.client.get(
            "/api/admin/ai/status",
            auth=(
                "admin",
                "admin-password-2026",
            ),
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()
        serialized = response.text

        self.assertEqual(
            body["active_provider"]["provider"],
            "mock",
        )
        self.assertEqual(
            body["local_model"]["asset_status"]["state"],
            "MISSING",
        )
        self.assertEqual(
            body["local_model"]["server_status"]["state"],
            "READY",
        )
        self.assertEqual(
            body["local_model"]["registration_status"]["state"],
            "REGISTERED",
        )
        self.assertEqual(
            body["local_model"]["inference_status"]["state"],
            "NOT_CHECKED",
        )
        self.assertNotIn(self.api_key, serialized)
        self.assertNotIn(str(PROJECT_ROOT), serialized)
        self.assertEqual(len(self.requests), 1)

    def test_inference_runs_only_when_admin_explicitly_requests_it(self):
        response = self.client.get(
            "/api/admin/ai/status?run_inference=true",
            auth=(
                "admin",
                "admin-password-2026",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["local_model"]["inference_status"]["state"],
            "READY",
        )
        self.assertEqual(
            [request.url.path for request in self.requests],
            ["/api/tags", "/api/chat"],
        )

    def test_health_does_not_probe_ollama(self):
        response = self.client.get("/actuator/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
