from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entities import (
    MESSAGE_ROLE_USER,
    ChatMessage,
    PsychologicalReport,
    UserAccount,
)
from app.services.chat_service import create_chat_message
from app.services.report_service import create_psychological_report
from app.services.risk_service import PsychologicalAssessment, assess_psychological_risk


@dataclass(frozen=True)
class ProcessedUserMessage:
    """一次用户消息处理产生的全部数据库对象"""

    user_message: ChatMessage
    assessment: PsychologicalAssessment
    report: PsychologicalReport | None


def process_user_message(
    database: Session,
    *,
    owner: UserAccount,
    session_public_id: str | UUID,
    content: str,
) -> ProcessedUserMessage:
    """保存用户消息、执行硬规则并创建必要的后台报告"""

    user_message = create_chat_message(
        database,
        owner=owner,
        session_public_id=session_public_id,
        role=MESSAGE_ROLE_USER,
        content=content,
    )

    assessment = assess_psychological_risk(user_message.content)

    report = create_psychological_report(
        database,
        message=user_message,
        assessment=assessment,
    )

    return ProcessedUserMessage(
        user_message=user_message,
        assessment=assessment,
        report=report,
    )
