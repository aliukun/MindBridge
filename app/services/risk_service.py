import unicodedata
from dataclasses import dataclass

from app.core.enums import RiskLevel

RISK_RULE_VERSION = "keyword_rule_v1"

NON_DIAGNOSTIC_DISCLAIMER = (
    "此结果只用于支持强度和人工跟进分流，不是医学或心理诊断，"
    "也不能替代心理咨询师、医生或当地紧急服务。"
)

HIGH_RISK_SIGNAL_GROUPS: dict[str, tuple[str, ...]] = {
    "SELF_HARM_OR_SUICIDE": (
        "自杀",
        "自残",
        "轻生",
        "不想活",
        "想死",
        "结束生命",
        "伤害自己",
        "杀了自己",
        "suicide",
        "kill myself",
        "end my life",
        "i want to die",
        "self harm",
        "self-harm",
        "hurt myself",
    ),
    "HARM_TO_OTHERS": (
        "伤害别人",
        "伤害他人",
        "杀了他",
        "杀了她",
        "同归于尽",
        "hurt someone",
        "kill him",
        "kill her",
        "kill them",
    ),
    "IMMEDIATE_DANGER": (
        "无法保证自己安全",
        "控制不住要伤害",
        "马上去死",
        "今晚就结束",
        "cannot keep myself safe",
    ),
}

MEDIUM_RISK_SIGNAL_GROUPS: dict[str, tuple[str, ...]] = {
    "SEVERE_DISTRESS": (
        "撑不住",
        "情绪崩溃",
        "每天都很难受",
        "痛苦得受不了",
        "can't cope",
        "cannot cope",
    ),
    "PERSISTENT_HOPELESSNESS": (
        "非常绝望",
        "没有希望",
        "活着没意思",
        "消失就好了",
        "hopeless",
        "not worth living",
    ),
    "FUNCTIONAL_IMPAIRMENT": (
        "长期失眠",
        "连续失眠",
        "无法上课",
        "不能上课",
        "吃不下饭",
        "无法正常生活",
    ),
}


@dataclass(frozen=True)
class PsychologicalAssessment:
    """硬规则生成的后台评估结果。"""

    risk_level: RiskLevel
    matched_signals: tuple[str, ...]
    summary: str
    rule_version: str

    @property
    def needs_support(self) -> bool:
        return self.risk_level in {
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
        }

    @property
    def immediate_support(self) -> bool:
        return self.risk_level is RiskLevel.HIGH


def _matched_signal_groups(
    normalized_text: str,
    groups: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """返回命中的类别名称，不返回或持久化具体关键词。"""

    return tuple(
        group_name
        for group_name, phrases in groups.items()
        if any(phrase.casefold() in normalized_text for phrase in phrases)
    )


def assess_psychological_risk(
    text: str,
) -> PsychologicalAssessment:
    """使用高风险优先的确定性规则评估一段文本。"""

    normalized_text = " ".join(
        unicodedata.normalize(
            "NFKC",
            text,
        )
        .casefold()
        .split()
    )

    if not normalized_text:
        raise ValueError("Text to assess must not be blank.")

    high_signals = _matched_signal_groups(
        normalized_text,
        HIGH_RISK_SIGNAL_GROUPS,
    )

    if high_signals:
        return PsychologicalAssessment(
            risk_level=RiskLevel.HIGH,
            matched_signals=high_signals,
            summary=(
                "检测到需要立即进行安全确认的表达；此结果是安全分流，不是临床诊断。"
            ),
            rule_version=RISK_RULE_VERSION,
        )

    medium_signals = _matched_signal_groups(
        normalized_text,
        MEDIUM_RISK_SIGNAL_GROUPS,
    )

    if medium_signals:
        return PsychologicalAssessment(
            risk_level=RiskLevel.MEDIUM,
            matched_signals=medium_signals,
            summary=("检测到较强或持续困扰的表达，建议尽快由现实中的人提供支持。"),
            rule_version=RISK_RULE_VERSION,
        )

    return PsychologicalAssessment(
        risk_level=RiskLevel.LOW,
        matched_signals=(),
        summary=("当前硬规则未检测到中高风险信号；这不代表风险一定不存在。"),
        rule_version=RISK_RULE_VERSION,
    )
