import json
import unittest
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.contracts import AiRequestOptions
from app.ai.errors import AiUnavailableError
from app.api.dependencies import get_ai_provider, get_ai_request_options
from app.core.bootstrap import create_schema
from app.core.database import Base, build_engine, get_db
from app.main import create_app
from app.models.entities import (
    ROLE_USER,
    ChatMessage,
    PsychologicalReport,
)
from app.services.ai_risk_service import (
    HIGH_RISK_SAFE_REPLY,
    MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
)
from app.services.privacy_service import (
    CAMPUS_ID_PLACEHOLDER,
    EMAIL_PLACEHOLDER,
    NATIONAL_ID_PLACEHOLDER,
    PHONE_PLACEHOLDER,
)
from app.services.user_service import create_user
from tests.ai_fakes import ScriptedAiProvider


def analysis_json(intent: str, risk_level: str) -> str:
    """生成符合严格分析契约的 Provider 测试响应。"""

    return json.dumps(
        {
            "intent": intent,
            "suggested_risk": risk_level,
            "summary": "仅供安全分流参考，不是诊断。",
        },
        ensure_ascii=False,
    )


class ChatTurnApiTests(unittest.TestCase):
    def setUp(self) -> None:
        """为每个测试创建隔离数据库、用户和可替换 Provider。"""

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

        def override_get_db() -> Generator[Session, None, None]:
            database = self.SessionTesting()

            try:
                yield database
            finally:
                database.close()

        self.provider = ScriptedAiProvider()
        self.application.dependency_overrides[get_db] = override_get_db
        self.application.dependency_overrides[get_ai_provider] = lambda: self.provider
        self.application.dependency_overrides[get_ai_request_options] = lambda: (
            AiRequestOptions(
                temperature=0.35,
                max_tokens=512,
            )
        )

        self.client = TestClient(self.application)
        self.student_auth = (
            "student",
            "student-password-2026",
        )
        self.other_auth = (
            "other",
            "other-password-2026",
        )

    def tearDown(self) -> None:
        self.client.close()
        self.application.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def create_session(self, *, auth=None) -> str:
        response = self.client.post(
            "/api/chat/sessions",
            json={"title": "Turn API tests"},
            auth=auth or self.student_auth,
        )

        self.assertEqual(response.status_code, 201)

        return response.json()["public_id"]

    def post_turn(
        self,
        session_public_id: str,
        content: str,
        *,
        auth=None,
    ):
        return self.client.post(
            f"/api/chat/sessions/{session_public_id}/turns",
            json={"content": content},
            auth=auth or self.student_auth,
        )

    def test_success_returns_only_public_turn_dto(self) -> None:
        self.provider.queue(
            analysis_json("CHAT", "LOW"),
            "我们可以从今天最想解决的一件事开始。",
        )
        public_id = self.create_session()

        response = self.post_turn(public_id, "今天课程有点多。")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(
            set(body),
            {"session", "assistant_message"},
        )
        self.assertEqual(
            set(body["session"]),
            {"public_id", "title", "created_at", "updated_at"},
        )
        self.assertEqual(
            set(body["assistant_message"]),
            {"role", "content", "created_at"},
        )
        self.assertEqual(body["session"]["public_id"], public_id)
        self.assertEqual(body["assistant_message"]["role"], "assistant")
        self.assertEqual(
            body["assistant_message"]["content"],
            "我们可以从今天最想解决的一件事开始。",
        )
        self.assertNotIn("risk_level", response.text)
        self.assertNotIn("matched_signals", response.text)

        with self.SessionTesting() as database:
            messages = list(
                database.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
            )

        self.assertEqual(
            [message.role for message in messages],
            ["user", "assistant"],
        )
        self.assertEqual(len(self.provider.requests), 2)

    def test_pii_only_reaches_provider_as_sanitized_copy(self) -> None:
        original_content = (
            "请联系 liukun@example.com，手机号 13800138000，"
            "身份证 11010519491231002X，学号：2026123456。"
        )
        raw_identifiers = (
            "liukun@example.com",
            "13800138000",
            "11010519491231002X",
            "2026123456",
        )
        placeholders = (
            EMAIL_PLACEHOLDER,
            PHONE_PLACEHOLDER,
            NATIONAL_ID_PLACEHOLDER,
            CAMPUS_ID_PLACEHOLDER,
        )
        self.provider.queue(
            analysis_json("CHAT", "LOW"),
            "我已经收到你的问题。",
        )
        public_id = self.create_session()

        response = self.post_turn(public_id, original_content)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.provider.requests), 2)

        provider_text = "\n".join(
            message.content
            for request in self.provider.requests
            for message in request.messages
        )
        provider_user_copies = [
            request.messages[-1].content for request in self.provider.requests
        ]

        for identifier in raw_identifiers:
            self.assertNotIn(identifier, provider_text)

        for sanitized_copy in provider_user_copies:
            for placeholder in placeholders:
                self.assertIn(placeholder, sanitized_copy)

        with self.SessionTesting() as database:
            stored_user_message = database.scalars(
                select(ChatMessage).where(ChatMessage.role == "user")
            ).one()

        self.assertEqual(stored_user_message.content, original_content)

    def test_low_provider_failure_returns_503_and_preserves_user_message(
        self,
    ) -> None:
        self.provider.queue(AiUnavailableError("offline"))
        public_id = self.create_session()

        response = self.post_turn(public_id, "今天课程有点多。")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "ai_service_unavailable")
        self.assertEqual(
            response.json()["detail"],
            "AI service is temporarily unavailable. Please try again later.",
        )
        self.assertEqual(len(self.provider.requests), 1)

        with self.SessionTesting() as database:
            messages = list(database.scalars(select(ChatMessage)).all())

        self.assertEqual(
            [(message.role, message.content) for message in messages],
            [("user", "今天课程有点多。")],
        )

    def test_hard_high_uses_fixed_reply_without_calling_offline_provider(
        self,
    ) -> None:
        self.provider.queue(AiUnavailableError("offline"))
        public_id = self.create_session()

        response = self.post_turn(public_id, "我不想活了。")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["assistant_message"]["content"],
            HIGH_RISK_SAFE_REPLY,
        )
        self.assertEqual(self.provider.requests, [])

        with self.SessionTesting() as database:
            messages = list(
                database.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
            )
            report = database.scalars(select(PsychologicalReport)).one()

        self.assertEqual(
            [message.role for message in messages],
            ["user", "assistant"],
        )
        self.assertEqual(report.risk_level, "HIGH")

    def test_hard_medium_uses_support_reply_when_provider_is_offline(
        self,
    ) -> None:
        self.provider.queue(AiUnavailableError("offline"))
        public_id = self.create_session()

        response = self.post_turn(
            public_id,
            "我连续失眠，已经无法正常生活。",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["assistant_message"]["content"],
            MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
        )
        self.assertEqual(len(self.provider.requests), 1)

        with self.SessionTesting() as database:
            messages = list(
                database.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
            )
            report = database.scalars(select(PsychologicalReport)).one()

        self.assertEqual(
            [message.role for message in messages],
            ["user", "assistant"],
        )
        self.assertEqual(report.risk_level, "MEDIUM")

    def test_other_users_session_returns_404_without_calling_provider(
        self,
    ) -> None:
        self.provider.queue(
            analysis_json("CHAT", "LOW"),
            "This reply must never be used.",
        )
        other_session_public_id = self.create_session(auth=self.other_auth)

        response = self.post_turn(
            other_session_public_id,
            "尝试访问别人的会话。",
            auth=self.student_auth,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "chat_session_not_found")
        self.assertEqual(self.provider.requests, [])

        with self.SessionTesting() as database:
            messages = list(database.scalars(select(ChatMessage)).all())

        self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()
