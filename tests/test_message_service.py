import unittest

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.bootstrap import create_schema
from app.core.database import Base, build_engine
from app.core.enums import RiskLevel
from app.models.entities import (
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_ROLE_USER,
    ROLE_USER,
    ChatMessage,
    PsychologicalReport,
)
from app.services.chat_service import (
    create_chat_message,
    create_chat_session,
    get_chat_history,
)
from app.services.message_service import (
    process_user_message,
)
from app.services.report_service import (
    create_psychological_report,
)
from app.services.risk_service import (
    assess_psychological_risk,
)
from app.services.user_service import create_user


class MessageServiceTests(unittest.TestCase):
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
                title="Risk assessment",
            )

            database.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

        self.engine.dispose()

    def test_low_message_creates_no_report(self):
        with self.SessionTesting() as database:
            result = process_user_message(
                database,
                owner=self.owner,
                session_public_id=(self.chat_session.public_id),
                content="今天课程有点多。",
            )

            database.commit()

            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertEqual(
            result.assessment.risk_level,
            RiskLevel.LOW,
        )

        self.assertIsNone(result.report)

        self.assertEqual(
            report_count,
            0,
        )

    def test_medium_message_creates_report_only(self):
        with self.SessionTesting() as database:
            result = process_user_message(
                database,
                owner=self.owner,
                session_public_id=(self.chat_session.public_id),
                content=("我连续失眠，已经无法正常生活。"),
            )

            database.commit()

        self.assertIsNotNone(result.report)

        assert result.report is not None

        self.assertEqual(
            result.report.risk_level,
            RiskLevel.MEDIUM.value,
        )

        self.assertIn(
            "FUNCTIONAL_IMPAIRMENT",
            result.report.matched_signals,
        )

    def test_high_message_creates_report_without_extra_message(
        self,
    ):
        with self.SessionTesting() as database:
            result = process_user_message(
                database,
                owner=self.owner,
                session_public_id=(self.chat_session.public_id),
                content="我不想活了。",
            )

            database.commit()

            history = get_chat_history(
                database,
                owner=self.owner,
                session_public_id=(self.chat_session.public_id),
            )

        self.assertIsNotNone(result.report)

        assert result.report is not None

        self.assertEqual(
            result.report.risk_level,
            RiskLevel.HIGH.value,
        )

        self.assertEqual(
            [message.role for message in history.messages],
            ["user"],
        )

    def test_caller_can_roll_back_the_whole_operation(
        self,
    ):
        with self.SessionTesting() as database:
            process_user_message(
                database,
                owner=self.owner,
                session_public_id=(self.chat_session.public_id),
                content="我不想活了。",
            )

            database.rollback()

            message_count = database.scalar(
                select(func.count()).select_from(ChatMessage)
            )

            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertEqual(message_count, 0)
        self.assertEqual(report_count, 0)

    def test_report_service_rejects_assistant_message(
        self,
    ):
        with self.SessionTesting() as database:
            assistant_message = create_chat_message(
                database,
                owner=self.owner,
                session_public_id=(self.chat_session.public_id),
                role=MESSAGE_ROLE_ASSISTANT,
                content="Assistant text",
            )

            assessment = assess_psychological_risk("我连续失眠，已经无法正常生活。")

            with self.assertRaisesRegex(
                ValueError,
                "require a user message",
            ):
                create_psychological_report(
                    database,
                    message=assistant_message,
                    assessment=assessment,
                )

            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertEqual(
            report_count,
            0,
        )

    def test_report_service_is_idempotent_for_same_message(
        self,
    ):
        with self.SessionTesting() as database:
            user_message = create_chat_message(
                database,
                owner=self.owner,
                session_public_id=(self.chat_session.public_id),
                role=MESSAGE_ROLE_USER,
                content=("我连续失眠，已经无法正常生活。"),
            )

            assessment = assess_psychological_risk(user_message.content)

            first = create_psychological_report(
                database,
                message=user_message,
                assessment=assessment,
            )

            second = create_psychological_report(
                database,
                message=user_message,
                assessment=assessment,
            )

            database.commit()

            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertIs(first, second)
        self.assertEqual(report_count, 1)


if __name__ == "__main__":
    unittest.main()
