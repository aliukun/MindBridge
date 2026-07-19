import json
import unittest
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.ai.contracts import AiRequestOptions
from app.ai.errors import AiUnavailableError
from app.core.bootstrap import create_schema
from app.core.database import Base, build_engine
from app.core.enums import RiskLevel
from app.models.entities import ROLE_USER, ChatMessage, PsychologicalReport
from app.services.ai_risk_service import (
    HIGH_RISK_SAFE_REPLY,
    MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
)
from app.services.chat_service import create_chat_session
from app.services.message_service import (
    process_user_message as real_process_user_message,
)
from app.services.report_service import (
    upsert_psychological_report as real_upsert_report,
)
from app.services.turn_service import TurnAiUnavailableError, TurnService
from app.services.user_service import create_user
from tests.ai_fakes import ScriptedAiProvider


def analysis_json(intent: str, risk_level: str) -> str:
    return json.dumps(
        {
            "intent": intent,
            "suggested_risk": risk_level,
            "summary": "仅供安全分流参考，不是诊断。",
        },
        ensure_ascii=False,
    )


class TurnServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = build_engine("sqlite+pysqlite:///:memory:")
        create_schema(self.engine)
        self.SessionTesting = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

        with self.SessionTesting() as database:
            self.owner = create_user(
                database,
                username="owner",
                display_name="Owner",
                password="owner-password-2026",
                roles={ROLE_USER},
            )
            self.chat_session = create_chat_session(
                database,
                owner=self.owner,
                title="Turn tests",
            )
            database.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    @staticmethod
    def service(provider: ScriptedAiProvider) -> TurnService:
        return TurnService(
            provider=provider,
            request_options=AiRequestOptions(
                temperature=0.4,
                max_tokens=512,
            ),
        )

    async def test_low_turn_uses_sanitized_copy_outside_transactions(self):
        content = (
            "请联系 liukun@example.com，手机号 13800138000，身份证 11010519491231002X。"
        )

        with self.SessionTesting() as database:
            transaction_states: list[bool] = []
            provider = ScriptedAiProvider(
                analysis_json("CHAT", "LOW"),
                "我们可以先从最困扰你的事情谈起。",
                on_complete=lambda _: transaction_states.append(
                    database.in_transaction()
                ),
            )
            result = await self.service(provider).process_turn(
                database,
                owner=self.owner,
                session_public_id=self.chat_session.public_id,
                content=content,
            )
            messages = list(
                database.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
            )

        sent_to_ai = "\n".join(
            message.content
            for request in provider.requests
            for message in request.messages
        )

        self.assertEqual(transaction_states, [False, False])
        self.assertEqual(len(provider.requests), 2)
        self.assertNotIn("liukun@example.com", sent_to_ai)
        self.assertNotIn("13800138000", sent_to_ai)
        self.assertNotIn("11010519491231002X", sent_to_ai)
        self.assertEqual(result.user_message.content, content)
        self.assertEqual(
            [message.role for message in messages],
            ["user", "assistant"],
        )
        self.assertIs(result.final_assessment.risk_level, RiskLevel.LOW)

    async def test_hard_high_never_calls_provider(self):
        with self.SessionTesting() as database:
            provider = ScriptedAiProvider()
            result = await self.service(provider).process_turn(
                database,
                owner=self.owner,
                session_public_id=self.chat_session.public_id,
                content="我不想活了。",
            )
            reports = list(database.scalars(select(PsychologicalReport)).all())

        self.assertEqual(provider.requests, [])
        self.assertIs(result.final_assessment.risk_level, RiskLevel.HIGH)
        self.assertEqual(result.assistant_message.content, HIGH_RISK_SAFE_REPLY)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].risk_level, "HIGH")

    async def test_model_high_uses_one_call_and_fixed_reply(self):
        with self.SessionTesting() as database:
            provider = ScriptedAiProvider(analysis_json("RISK", "HIGH"))
            result = await self.service(provider).process_turn(
                database,
                owner=self.owner,
                session_public_id=self.chat_session.public_id,
                content="最近心情不太好。",
            )
            report = database.scalars(select(PsychologicalReport)).one()

        self.assertEqual(len(provider.requests), 1)
        self.assertTrue(result.model_raised_risk)
        self.assertEqual(result.assistant_message.content, HIGH_RISK_SAFE_REPLY)
        self.assertEqual(report.risk_level, "HIGH")

    async def test_hard_medium_analysis_failure_uses_support_fallback(self):
        with self.SessionTesting() as database:
            provider = ScriptedAiProvider(AiUnavailableError("offline"))
            result = await self.service(provider).process_turn(
                database,
                owner=self.owner,
                session_public_id=self.chat_session.public_id,
                content="我连续失眠，已经无法正常生活。",
            )

        self.assertEqual(len(provider.requests), 1)
        self.assertTrue(result.provider_fallback_used)
        self.assertEqual(
            result.assistant_message.content,
            MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
        )

    async def test_low_analysis_failure_preserves_user_and_raises(self):
        with self.SessionTesting() as database:
            provider = ScriptedAiProvider(AiUnavailableError("offline"))

            with self.assertRaises(TurnAiUnavailableError):
                await self.service(provider).process_turn(
                    database,
                    owner=self.owner,
                    session_public_id=self.chat_session.public_id,
                    content="今天课程有点多。",
                )

            messages = list(database.scalars(select(ChatMessage)).all())

        self.assertEqual([message.role for message in messages], ["user"])

    async def test_model_medium_reply_failure_keeps_upgrade(self):
        with self.SessionTesting() as database:
            transaction_states: list[bool] = []
            provider = ScriptedAiProvider(
                analysis_json("CONSULT", "MEDIUM"),
                AiUnavailableError("reply offline"),
                on_complete=lambda _: transaction_states.append(
                    database.in_transaction()
                ),
            )
            result = await self.service(provider).process_turn(
                database,
                owner=self.owner,
                session_public_id=self.chat_session.public_id,
                content="最近心情有些低落。",
            )
            report = database.scalars(select(PsychologicalReport)).one()

        self.assertEqual(transaction_states, [False, False])
        self.assertEqual(report.risk_level, "MEDIUM")
        self.assertEqual(
            result.assistant_message.content,
            MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
        )

    async def test_bad_analysis_json_falls_back_then_replies(self):
        with self.SessionTesting() as database:
            provider = ScriptedAiProvider(
                "not-json",
                "结构化分析失败后，普通回复仍然可用。",
            )
            result = await self.service(provider).process_turn(
                database,
                owner=self.owner,
                session_public_id=self.chat_session.public_id,
                content="今天课程有点多。",
            )

        self.assertEqual(len(provider.requests), 2)
        self.assertIs(result.final_assessment.risk_level, RiskLevel.LOW)
        self.assertFalse(result.model_raised_risk)

    async def test_low_reply_failure_preserves_user_and_raises(self):
        with self.SessionTesting() as database:
            provider = ScriptedAiProvider(
                analysis_json("CHAT", "LOW"),
                AiUnavailableError("reply offline"),
            )

            with self.assertRaises(TurnAiUnavailableError):
                await self.service(provider).process_turn(
                    database,
                    owner=self.owner,
                    session_public_id=self.chat_session.public_id,
                    content="今天课程有点多。",
                )

            messages = list(database.scalars(select(ChatMessage)).all())

        self.assertEqual([message.role for message in messages], ["user"])

    async def test_transaction_a_failure_rolls_back_everything(self):
        def fail_transaction_a(
            database,
            *,
            owner,
            session_public_id,
            content,
        ):
            real_process_user_message(
                database,
                owner=owner,
                session_public_id=session_public_id,
                content=content,
            )
            raise RuntimeError("transaction A failed")

        with self.SessionTesting() as database:
            provider = ScriptedAiProvider()

            with patch(
                "app.services.turn_service.process_user_message",
                side_effect=fail_transaction_a,
            ):
                with self.assertRaisesRegex(RuntimeError, "transaction A failed"):
                    await self.service(provider).process_turn(
                        database,
                        owner=self.owner,
                        session_public_id=self.chat_session.public_id,
                        content="我不想活了。",
                    )

            message_count = database.scalar(
                select(func.count()).select_from(ChatMessage)
            )
            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertEqual(message_count, 0)
        self.assertEqual(report_count, 0)
        self.assertEqual(provider.requests, [])

    async def test_transaction_b_failure_keeps_a_only(self):
        def fail_transaction_b(database, *, message, assessment):
            real_upsert_report(
                database,
                message=message,
                assessment=assessment,
            )
            raise RuntimeError("transaction B failed")

        with self.SessionTesting() as database:
            provider = ScriptedAiProvider(analysis_json("CONSULT", "MEDIUM"))

            with patch(
                "app.services.turn_service.upsert_psychological_report",
                side_effect=fail_transaction_b,
            ):
                with self.assertRaisesRegex(RuntimeError, "transaction B failed"):
                    await self.service(provider).process_turn(
                        database,
                        owner=self.owner,
                        session_public_id=self.chat_session.public_id,
                        content="最近心情有些低落。",
                    )

            messages = list(database.scalars(select(ChatMessage)).all())
            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertEqual([message.role for message in messages], ["user"])
        self.assertEqual(report_count, 0)

    async def test_transaction_c_failure_keeps_a_and_b(self):
        with self.SessionTesting() as database:
            provider = ScriptedAiProvider(
                analysis_json("CONSULT", "MEDIUM"),
                "一条正常回复。",
            )

            with patch(
                "app.services.turn_service.create_chat_message",
                side_effect=RuntimeError("transaction C failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "transaction C failed"):
                    await self.service(provider).process_turn(
                        database,
                        owner=self.owner,
                        session_public_id=self.chat_session.public_id,
                        content="最近心情有些低落。",
                    )

            messages = list(database.scalars(select(ChatMessage)).all())
            reports = list(database.scalars(select(PsychologicalReport)).all())

        self.assertEqual([message.role for message in messages], ["user"])
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].risk_level, "MEDIUM")


if __name__ == "__main__":
    unittest.main()
