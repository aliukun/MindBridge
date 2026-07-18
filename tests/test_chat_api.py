import unittest
from collections.abc import Generator
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session, sessionmaker

from app.core.bootstrap import create_schema
from app.core.database import (
    Base,
    build_engine,
    get_db,
)
from app.main import create_app
from app.models.entities import ROLE_USER, PsychologicalReport, MESSAGE_ROLE_USER, ChatMessage
from app.services.chat_service import create_chat_message
from app.services.user_service import create_user


class ChatApiTests(unittest.TestCase):
    def setUp(self):
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
                display_name="Student",
                password="student-password-2026",
                roles={ROLE_USER},
            )

            create_user(
                database,
                username="other",
                display_name="Other",
                password="other-password-2026",
                roles={ROLE_USER},
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

        self.student_auth = (
            "student",
            "student-password-2026",
        )

        self.other_auth = (
            "other",
            "other-password-2026",
        )

    def tearDown(self):
        self.client.close()

        self.application.dependency_overrides.clear()

        Base.metadata.drop_all(
            bind=self.engine
        )

        self.engine.dispose()

    def create_session(
        self,
        auth=None,
    ) -> str:
        response = self.client.post(
            "/api/chat/sessions",
            json={
                "title": "Test session",
            },
            auth=auth or self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        return response.json()["public_id"]

    def test_authentication_is_required(self):
        response = self.client.post(
            "/api/chat/sessions",
            json={
                "title": "Private",
            },
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_create_session_returns_only_public_fields(self):
        response = self.client.post(
            "/api/chat/sessions",
            json={
                "title": "  My session  ",
            },
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        body = response.json()

        self.assertEqual(
            body["title"],
            "My session",
        )

        self.assertNotIn("id", body)
        self.assertNotIn("user_id", body)

    def test_blank_title_is_rejected(self):
        response = self.client.post(
            "/api/chat/sessions",
            json={
                "title": "   ",
            },
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            422,
        )

    def test_client_saves_user_message_and_reads_history(
        self,
    ):
        public_id = self.create_session()

        response = self.client.post(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            json={
                "content": "  Hello  ",
            },
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            response.json()["role"],
            "user",
        )

        self.assertNotIn(
            "risk_level",
            response.json(),
        )

        self.assertNotIn(
            "matched_signals",
            response.json(),
        )

        history = self.client.get(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            auth=self.student_auth,
        )

        self.assertEqual(
            history.status_code,
            200,
        )

        self.assertEqual(
            history.json()["messages"][0]["content"],
            "Hello",
        )

    def test_client_cannot_choose_assistant_role(self):
        public_id = self.create_session()

        response = self.client.post(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            json={
                "content": "Forged",
                "role": "assistant",
                "risk_level": "LOW",
                "matched_signals": [],
            },
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            422,
        )

    def test_owner_cannot_post_to_another_users_session(
        self,
    ):
        public_id = self.create_session(
            auth=self.other_auth
        )

        response = self.client.post(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            json={
                "content": "Intrusion",
            },
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_owner_cannot_read_another_users_session(
        self,
    ):
        public_id = self.create_session(
            auth=self.other_auth
        )

        response = self.client.get(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_invalid_and_unknown_public_ids_are_safe(self):
        malformed = self.client.get(
            (
                "/api/chat/sessions/"
                "not-a-uuid/messages"
            ),
            auth=self.student_auth,
        )

        unknown = self.client.get(
            (
                f"/api/chat/sessions/"
                f"{uuid4()}/messages"
            ),
            auth=self.student_auth,
        )

        self.assertEqual(
            malformed.status_code,
            422,
        )

        self.assertEqual(
            unknown.status_code,
            404,
        )

    def test_medium_message_creates_hidden_report(self):
        public_id = self.create_session()

        response = self.client.post(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            json={
                "content": (
                    "我连续失眠，已经无法正常生活。"
                ),
            },
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertNotIn(
            "risk_level",
            response.json(),
        )

        with self.SessionTesting() as database:
            reports = list(
                database.scalars(
                    select(PsychologicalReport)
                ).all()
            )

        self.assertEqual(
            len(reports),
            1,
        )

        self.assertEqual(
            reports[0].risk_level,
            "MEDIUM",
        )

    def test_high_message_creates_hidden_report_only(
            self,
    ):
        public_id = self.create_session()

        response = self.client.post(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            json={
                "content": "我不想活了。",
            },
            auth=self.student_auth,
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        response_text = response.text

        self.assertNotIn(
            "HIGH",
            response_text,
        )

        self.assertNotIn(
            "risk_level",
            response_text,
        )

        self.assertNotIn(
            "matched_signals",
            response_text,
        )

        history = self.client.get(
            (
                f"/api/chat/sessions/"
                f"{public_id}/messages"
            ),
            auth=self.student_auth,
        )

        self.assertEqual(
            history.status_code,
            200,
        )

        messages = history.json()["messages"]

        self.assertEqual(
            [
                message["role"]
                for message in messages
            ],
            ["user"],
        )

        with self.SessionTesting() as database:
            report = database.scalars(
                select(PsychologicalReport)
            ).one()

        self.assertEqual(
            report.risk_level,
            "HIGH",
        )

    def test_route_rolls_back_all_rows_when_processing_fails(
            self,
    ):
        public_id = self.create_session()

        def fail_after_message(
                database,
                *,
                owner,
                session_public_id,
                content,
        ):
            create_chat_message(
                database,
                owner=owner,
                session_public_id=session_public_id,
                role=MESSAGE_ROLE_USER,
                content=content,
            )

            raise RuntimeError(
                "simulated failure"
            )

        with patch(
                "app.api.routes.process_user_message",
                side_effect=fail_after_message,
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    (
                        f"/api/chat/sessions/"
                        f"{public_id}/messages"
                    ),
                    json={
                        "content": "我不想活了。",
                    },
                    auth=self.student_auth,
                )

        with self.SessionTesting() as database:
            message_count = database.scalar(
                select(func.count()).select_from(
                    ChatMessage
                )
            )

            report_count = database.scalar(
                select(func.count()).select_from(
                    PsychologicalReport
                )
            )

        self.assertEqual(message_count, 0)
        self.assertEqual(report_count, 0)

if __name__ == "__main__":
    unittest.main()