import unittest
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.bootstrap import create_schema
from app.core.database import (
    Base,
    build_engine,
    get_db,
)
from app.main import create_app
from app.models.entities import (
    ROLE_ADMIN,
    ROLE_USER,
)
from app.services.user_service import create_user


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        """每个测试使用独立的内存数据库。"""

        self.engine = build_engine(
            "sqlite+pysqlite:///:memory:",
        )

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

        self.application = create_app()

        def override_get_db(
        ) -> Generator[Session, None, None]:
            database = self.SessionTesting()

            try:
                yield database
            finally:
                database.close()

        self.application.dependency_overrides[
            get_db
        ] = override_get_db

        self.client = TestClient(
            self.application
        )

    def tearDown(self):
        self.client.close()

        self.application.dependency_overrides.clear()

        Base.metadata.drop_all(
            bind=self.engine
        )

        self.engine.dispose()

    def test_missing_credentials_returns_401(self):
        response = self.client.get(
            "/api/users/me"
        )

        self.assertEqual(
            response.status_code,
            401,
        )

        self.assertIn(
            "Basic",
            response.headers["www-authenticate"],
        )

    def test_wrong_password_returns_401(self):
        response = self.client.get(
            "/api/users/me",
            auth=(
                "student",
                "wrong-password",
            ),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

        self.assertEqual(
            response.json()["detail"],
            "Incorrect username or password",
        )

    def test_unknown_username_returns_same_401(self):
        response = self.client.get(
            "/api/users/me",
            auth=(
                "unknown",
                "wrong-password",
            ),
        )

        self.assertEqual(
            response.status_code,
            401,
        )

        self.assertEqual(
            response.json()["detail"],
            "Incorrect username or password",
        )

    def test_student_can_read_profile(self):
        response = self.client.get(
            "/api/users/me",
            auth=(
                "student",
                "student-password-2026",
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["username"],
            "student",
        )

        self.assertEqual(
            body["display_name"],
            "Test Student",
        )

        self.assertEqual(
            body["roles"],
            ["ROLE_USER"],
        )

        self.assertNotIn(
            "password_hash",
            body,
        )

    def test_student_cannot_access_admin_route(self):
        response = self.client.get(
            "/api/admin/ping",
            auth=(
                "student",
                "student-password-2026",
            ),
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            response.json()["detail"],
            "Administrator role required",
        )

    def test_admin_can_access_admin_route(self):
        response = self.client.get(
            "/api/admin/ping",
            auth=(
                "admin",
                "admin-password-2026",
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json(),
            {
                "status": "ADMIN_OK",
                "username": "admin",
            },
        )


if __name__ == "__main__":
    unittest.main()