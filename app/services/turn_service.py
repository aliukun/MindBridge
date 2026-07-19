from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.contracts import AiRequestOptions
from app.ai.errors import AiProviderError
from app.ai.parsing import ModelAnalysisParseError, parse_model_analysis
from app.ai.prompts import build_analysis_request, build_reply_request
from app.ai.providers.base import AiProvider
from app.core.enums import RiskLevel
from app.models.entities import (
    MESSAGE_ROLE_ASSISTANT,
    ChatMessage,
    ChatSession,
    UserAccount,
)
from app.services.ai_risk_service import (
    HIGH_RISK_SAFE_REPLY,
    MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
    merge_risk_assessment,
    select_response_intent,
)
from app.services.chat_service import create_chat_message
from app.services.message_service import process_user_message
from app.services.privacy_service import sanitize_for_ai
from app.services.report_service import upsert_psychological_report
from app.services.risk_service import PsychologicalAssessment


class TurnAiUnavailableError(RuntimeError):
    """普通低风险轮次无法得到真实模型回复。"""


@dataclass(frozen=True)
class CompletedChatTurn:
    """TurnService 的内部完成结果。"""

    session: ChatSession
    user_message: ChatMessage
    assistant_message: ChatMessage
    hard_rule_assessment: PsychologicalAssessment
    final_assessment: PsychologicalAssessment
    model_raised_risk: bool
    provider_fallback_used: bool


class TurnService:
    """编排一次安全、非流式聊天轮次。"""

    def __init__(
        self,
        *,
        provider: AiProvider,
        request_options: AiRequestOptions,
    ) -> None:
        self._provider = provider
        self._request_options = request_options

    def _commit_assistant_message(
        self,
        database: Session,
        *,
        owner: UserAccount,
        session_public_id: str | UUID,
        content: str,
    ) -> ChatMessage:
        """事务 C：只保存最终完整助手消息。"""

        try:
            assistant_message = create_chat_message(
                database,
                owner=owner,
                session_public_id=session_public_id,
                role=MESSAGE_ROLE_ASSISTANT,
                content=content,
            )
            database.commit()
        except Exception:
            database.rollback()
            raise

        return assistant_message

    def _completed_turn(
        self,
        database: Session,
        *,
        owner: UserAccount,
        session_public_id: str | UUID,
        session: ChatSession,
        user_message: ChatMessage,
        hard_rule_assessment: PsychologicalAssessment,
        final_assessment: PsychologicalAssessment,
        assistant_content: str,
        model_raised_risk: bool,
        provider_fallback_used: bool,
    ) -> CompletedChatTurn:
        assistant_message = self._commit_assistant_message(
            database,
            owner=owner,
            session_public_id=session_public_id,
            content=assistant_content,
        )

        return CompletedChatTurn(
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            hard_rule_assessment=hard_rule_assessment,
            final_assessment=final_assessment,
            model_raised_risk=model_raised_risk,
            provider_fallback_used=provider_fallback_used,
        )

    async def process_turn(
        self,
        database: Session,
        *,
        owner: UserAccount,
        session_public_id: str | UUID,
        content: str,
    ) -> CompletedChatTurn:
        """保存原文、执行模型调用并保存安全的最终回复。"""

        # 事务 A：原始用户消息与硬规则报告共同提交。
        try:
            processed = process_user_message(
                database,
                owner=owner,
                session_public_id=session_public_id,
                content=content,
            )
            session = processed.user_message.session
            original_content = processed.user_message.content
            database.commit()
        except Exception:
            database.rollback()
            raise

        hard_assessment = processed.assessment

        # 硬规则 HIGH 不把数据发送给 Provider。
        if hard_assessment.risk_level is RiskLevel.HIGH:
            return self._completed_turn(
                database,
                owner=owner,
                session_public_id=session_public_id,
                session=session,
                user_message=processed.user_message,
                hard_rule_assessment=hard_assessment,
                final_assessment=hard_assessment,
                assistant_content=HIGH_RISK_SAFE_REPLY,
                model_raised_risk=False,
                provider_fallback_used=False,
            )

        sanitized_input = sanitize_for_ai(original_content)
        analysis_request = build_analysis_request(
            sanitized_input,
            options=self._request_options,
        )

        # 事务外：一次低随机性的结构化分析调用。
        try:
            analysis_completion = await self._provider.complete(analysis_request)
        except AiProviderError:
            if hard_assessment.risk_level is RiskLevel.MEDIUM:
                return self._completed_turn(
                    database,
                    owner=owner,
                    session_public_id=session_public_id,
                    session=session,
                    user_message=processed.user_message,
                    hard_rule_assessment=hard_assessment,
                    final_assessment=hard_assessment,
                    assistant_content=MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
                    model_raised_risk=False,
                    provider_fallback_used=True,
                )

            raise TurnAiUnavailableError(
                "AI service is temporarily unavailable."
            ) from None

        try:
            model_analysis = parse_model_analysis(analysis_completion.text)
        except ModelAnalysisParseError:
            model_analysis = None

        merged = merge_risk_assessment(
            hard_assessment,
            model_analysis,
        )

        # 事务 B：先保存模型带来的风险升级，再等待回复生成。
        if merged.model_raised_risk:
            try:
                upsert_psychological_report(
                    database,
                    message=processed.user_message,
                    assessment=merged.final_assessment,
                )
                database.commit()
            except Exception:
                database.rollback()
                raise

        final_assessment = merged.final_assessment

        if final_assessment.risk_level is RiskLevel.HIGH:
            return self._completed_turn(
                database,
                owner=owner,
                session_public_id=session_public_id,
                session=session,
                user_message=processed.user_message,
                hard_rule_assessment=hard_assessment,
                final_assessment=final_assessment,
                assistant_content=HIGH_RISK_SAFE_REPLY,
                model_raised_risk=merged.model_raised_risk,
                provider_fallback_used=False,
            )

        response_intent = select_response_intent(
            model_analysis,
            final_assessment.risk_level,
        )
        reply_request = build_reply_request(
            sanitized_input,
            intent=response_intent,
            final_risk=final_assessment.risk_level,
            options=self._request_options,
        )

        # 事务外：至多一次自然语言回复调用。
        try:
            reply_completion = await self._provider.complete(reply_request)
            assistant_content = reply_completion.text
            provider_fallback_used = False
        except AiProviderError:
            if final_assessment.risk_level is RiskLevel.MEDIUM:
                assistant_content = MEDIUM_PROVIDER_UNAVAILABLE_REPLY
                provider_fallback_used = True
            else:
                raise TurnAiUnavailableError(
                    "AI service is temporarily unavailable."
                ) from None

        return self._completed_turn(
            database,
            owner=owner,
            session_public_id=session_public_id,
            session=session,
            user_message=processed.user_message,
            hard_rule_assessment=hard_assessment,
            final_assessment=final_assessment,
            assistant_content=assistant_content,
            model_raised_risk=merged.model_raised_risk,
            provider_fallback_used=provider_fallback_used,
        )
