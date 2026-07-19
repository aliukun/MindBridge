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
from app.services.chat_service import create_chat_message, create_chat_session
from app.services.report_service import (
    create_psychological_report,
    upsert_psychological_report,
)
from app.services.risk_service import (
    PsychologicalAssessment,
    assess_psychological_risk,
)
from app.services.user_service import create_user


class ReportServiceTests(unittest.TestCase):
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
                title="Report tests",
            )
            database.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _message(
        self,
        database,
        *,
        role=MESSAGE_ROLE_USER,
    ) -> ChatMessage:
        return create_chat_message(
            database,
            owner=self.owner,
            session_public_id=self.chat_session.public_id,
            role=role,
            content="我连续失眠，已经无法正常生活。",
        )

    def test_existing_medium_report_is_upgraded_to_high_once(self):
        with self.SessionTesting() as database:
            message = self._message(database)
            medium = assess_psychological_risk(message.content)
            first = create_psychological_report(
                database,
                message=message,
                assessment=medium,
            )
            high = PsychologicalAssessment(
                risk_level=RiskLevel.HIGH,
                matched_signals=(),
                summary="模型建议提高支持强度；这不是诊断。",
                rule_version="keyword_rule_v1+model_risk_advisory_v1",
            )
            second = upsert_psychological_report(
                database,
                message=message,
                assessment=high,
            )
            database.commit()
            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertIs(first, second)
        assert second is not None
        self.assertEqual(second.risk_level, "HIGH")
        self.assertIn("FUNCTIONAL_IMPAIRMENT", second.matched_signals)
        self.assertEqual(report_count, 1)

    def test_existing_high_report_is_never_downgraded(self):
        with self.SessionTesting() as database:
            message = self._message(database)
            high = PsychologicalAssessment(
                risk_level=RiskLevel.HIGH,
                matched_signals=(),
                summary="固定高风险分流摘要。",
                rule_version="model_risk_advisory_v1",
            )
            report = upsert_psychological_report(
                database,
                message=message,
                assessment=high,
            )
            original_method = report.assessment_method if report else None
            medium = assess_psychological_risk(message.content)
            same_report = upsert_psychological_report(
                database,
                message=message,
                assessment=medium,
            )
            database.commit()

        self.assertIs(report, same_report)
        assert same_report is not None
        self.assertEqual(same_report.risk_level, "HIGH")
        self.assertEqual(same_report.assessment_method, original_method)

    def test_retry_in_a_new_session_remains_idempotent(self):
        medium = PsychologicalAssessment(
            risk_level=RiskLevel.MEDIUM,
            matched_signals=(),
            summary="固定模型升级摘要。",
            rule_version="keyword_rule_v1+model_risk_advisory_v1",
        )

        with self.SessionTesting() as database:
            message = self._message(database)
            upsert_psychological_report(
                database,
                message=message,
                assessment=medium,
            )
            database.commit()
            message_id = message.id

        with self.SessionTesting() as database:
            message = database.get(ChatMessage, message_id)
            assert message is not None
            upsert_psychological_report(
                database,
                message=message,
                assessment=medium,
            )
            database.commit()
            report_count = database.scalar(
                select(func.count()).select_from(PsychologicalReport)
            )

        self.assertEqual(report_count, 1)

    def test_low_candidate_does_not_remove_existing_report(self):
        with self.SessionTesting() as database:
            message = self._message(database)
            medium = assess_psychological_risk(message.content)
            report = upsert_psychological_report(
                database,
                message=message,
                assessment=medium,
            )
            low = PsychologicalAssessment(
                risk_level=RiskLevel.LOW,
                matched_signals=(),
                summary="低风险候选。",
                rule_version="test_rule_v1",
            )
            same_report = upsert_psychological_report(
                database,
                message=message,
                assessment=low,
            )

        self.assertIs(report, same_report)
        assert same_report is not None
        self.assertEqual(same_report.risk_level, "MEDIUM")

    def test_invalid_report_metadata_is_rejected(self):
        invalid_assessments = (
            PsychologicalAssessment(
                risk_level=RiskLevel.MEDIUM,
                matched_signals=(),
                summary="summary",
                rule_version="   ",
            ),
            PsychologicalAssessment(
                risk_level=RiskLevel.MEDIUM,
                matched_signals=(),
                summary="   ",
                rule_version="rule_v1",
            ),
            PsychologicalAssessment(
                risk_level=RiskLevel.MEDIUM,
                matched_signals=("INVALID,SIGNAL",),
                summary="summary",
                rule_version="rule_v1",
            ),
        )

        for assessment in invalid_assessments:
            with self.subTest(assessment=assessment):
                with self.SessionTesting() as database:
                    message = self._message(database)

                    with self.assertRaises(ValueError):
                        upsert_psychological_report(
                            database,
                            message=message,
                            assessment=assessment,
                        )

    def test_assistant_message_is_still_rejected(self):
        with self.SessionTesting() as database:
            message = self._message(
                database,
                role=MESSAGE_ROLE_ASSISTANT,
            )
            assessment = assess_psychological_risk("我连续失眠，已经无法正常生活。")

            with self.assertRaisesRegex(ValueError, "require a user message"):
                upsert_psychological_report(
                    database,
                    message=message,
                    assessment=assessment,
                )


if __name__ == "__main__":
    unittest.main()
