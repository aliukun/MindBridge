from dataclasses import dataclass

from app.ai.parsing import ModelAnalysis
from app.core.enums import IntentType, RiskLevel
from app.services.risk_service import PsychologicalAssessment

MODEL_RISK_ADVISORY_VERSION = "model_risk_advisory_v1"

MODEL_RISK_UPGRADE_SUMMARY = (
    "模型建议提高支持优先级；该结果只用于安全分流，不是医学或心理诊断。"
)

HIGH_RISK_SAFE_REPLY = (
    "谢谢你愿意告诉我这些。现在最重要的是先确保你此刻的安全。"
    "请尽快走到有人的地方，马上联系一位你信任的人，并联系学校心理中心、"
    "辅导员或其他现实中的支持人员。"
    "如果你可能马上伤害自己或他人，请立即拨打 120 或 110，"
    "或者前往最近的急诊。"
    "你现在是否能够马上联系到一个可以陪在你身边的人？"
)

MEDIUM_PROVIDER_UNAVAILABLE_REPLY = (
    "我听见你现在承受着不小的压力。AI 服务暂时不可用，"
    "所以我目前不能生成个性化回复，但你不必独自承担。"
    "请先联系一位你信任的人，并尽快联系学校心理中心、"
    "辅导员或专业支持人员。"
    "如果情况开始影响你或他人的当下安全，请立即寻求当地紧急帮助。"
)

_RISK_PRIORITY = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}


@dataclass(frozen=True)
class MergedRiskAssessment:
    """硬规则与模型建议合并后的单调安全结果。"""

    final_assessment: PsychologicalAssessment
    model_suggested_risk: RiskLevel | None
    model_raised_risk: bool


def risk_priority(level: RiskLevel) -> int:
    """返回稳定风险顺序。"""

    return _RISK_PRIORITY[level]


def merge_risk_assessment(
    hard_rule_assessment: PsychologicalAssessment,
    model_analysis: ModelAnalysis | None,
) -> MergedRiskAssessment:
    """模型可以提高但不能降低硬规则风险。"""

    model_suggested_risk = (
        model_analysis.suggested_risk if model_analysis is not None else None
    )

    final_risk = hard_rule_assessment.risk_level
    model_raised_risk = False

    if model_suggested_risk is not None and risk_priority(
        model_suggested_risk
    ) > risk_priority(final_risk):
        final_risk = model_suggested_risk
        model_raised_risk = True

    if model_raised_risk:
        final_summary = f"{hard_rule_assessment.summary} {MODEL_RISK_UPGRADE_SUMMARY}"

        rule_version = (
            f"{hard_rule_assessment.rule_version}+{MODEL_RISK_ADVISORY_VERSION}"
        )
    else:
        final_summary = hard_rule_assessment.summary
        rule_version = hard_rule_assessment.rule_version

    final_assessment = PsychologicalAssessment(
        risk_level=final_risk,
        matched_signals=hard_rule_assessment.matched_signals,
        summary=final_summary,
        rule_version=rule_version,
    )

    return MergedRiskAssessment(
        final_assessment=final_assessment,
        model_suggested_risk=model_suggested_risk,
        model_raised_risk=model_raised_risk,
    )


def select_response_intent(
    model_analysis: ModelAnalysis | None,
    final_risk: RiskLevel,
) -> IntentType:
    """最终风险优先于模型的普通意图建议。"""

    if final_risk is RiskLevel.HIGH:
        return IntentType.RISK

    if final_risk is RiskLevel.MEDIUM:
        return IntentType.CONSULT

    if model_analysis is None:
        return IntentType.CHAT

    return model_analysis.intent
