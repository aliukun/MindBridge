from sqlalchemy.orm import Session

from app.core.enums import RiskLevel
from app.models.entities import (
    MESSAGE_ROLE_USER,
    ChatMessage,
    PsychologicalReport,
)
from app.services.ai_risk_service import risk_priority
from app.services.risk_service import PsychologicalAssessment

MAX_ASSESSMENT_METHOD_LENGTH = 64
MAX_MATCHED_SIGNALS_CSV_LENGTH = 512


def _normalized_report_values(
    assessment: PsychologicalAssessment,
) -> tuple[str, str, tuple[str, ...]]:
    assessment_method = assessment.rule_version.strip()
    summary = assessment.summary.strip()
    matched_signals = tuple(
        sorted(
            {signal.strip() for signal in assessment.matched_signals if signal.strip()}
        )
    )

    if not assessment_method:
        raise ValueError("Assessment method must not be blank.")

    if len(assessment_method) > MAX_ASSESSMENT_METHOD_LENGTH:
        raise ValueError("Assessment method is too long.")

    if not summary:
        raise ValueError("Assessment summary must not be blank.")

    if any("," in signal for signal in matched_signals):
        raise ValueError("Matched signal names must not contain commas.")

    if len(",".join(matched_signals)) > MAX_MATCHED_SIGNALS_CSV_LENGTH:
        raise ValueError("Matched signals are too long.")

    return assessment_method, summary, matched_signals


def upsert_psychological_report(
    database: Session,
    *,
    message: ChatMessage,
    assessment: PsychologicalAssessment,
) -> PsychologicalReport | None:
    """幂等创建或单调升级报告；只 flush，不 commit。"""

    if message.role != MESSAGE_ROLE_USER:
        raise ValueError("Psychological reports require a user message.")

    existing_report = message.assessment_report

    if assessment.risk_level is RiskLevel.LOW:
        return existing_report

    assessment_method, summary, matched_signals = _normalized_report_values(assessment)

    if existing_report is None:
        report = PsychologicalReport(
            message=message,
            risk_level=assessment.risk_level.value,
            assessment_method=assessment_method,
            summary=summary,
        )
        report.matched_signals = list(matched_signals)

        database.add(report)
        database.flush()

        return report

    current_level = RiskLevel(existing_report.risk_level)

    if risk_priority(assessment.risk_level) <= risk_priority(current_level):
        return existing_report

    existing_report.risk_level = assessment.risk_level.value
    existing_report.assessment_method = assessment_method
    existing_report.summary = summary
    existing_report.matched_signals = [
        *existing_report.matched_signals,
        *matched_signals,
    ]

    database.flush()

    return existing_report


def create_psychological_report(
    database: Session,
    *,
    message: ChatMessage,
    assessment: PsychologicalAssessment,
) -> PsychologicalReport | None:
    """兼容已有消息处理流程，只为中、高风险创建报告。"""

    if message.role != MESSAGE_ROLE_USER:
        raise ValueError("Psychological reports require a user message.")

    if assessment.risk_level is RiskLevel.LOW:
        return None

    return upsert_psychological_report(
        database,
        message=message,
        assessment=assessment,
    )
