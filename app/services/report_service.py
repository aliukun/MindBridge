from sqlalchemy.orm import Session

from app.core.enums import RiskLevel
from app.models.entities import MESSAGE_ROLE_USER, ChatMessage, PsychologicalReport
from app.services.risk_service import PsychologicalAssessment


def create_psychological_report(
    database: Session,
    *,
    message: ChatMessage,
    assessment: PsychologicalAssessment,
) -> PsychologicalReport | None:
    """只为中、高风险用户消息创建后台消息"""

    if message.role != MESSAGE_ROLE_USER:
        raise ValueError("Psychological reports require a user message.")

    if assessment.risk_level is RiskLevel.LOW:
        return None

    existing_report = message.assessment_report

    if existing_report is not None:
        return existing_report

    report = PsychologicalReport(
        message=message,
        risk_level=str(assessment.risk_level.value),
        assessment_method=assessment.rule_version,
        summary=assessment.summary,
    )

    report.matched_signals = list(assessment.matched_signals)

    database.add(report)
    database.flush()

    return report
