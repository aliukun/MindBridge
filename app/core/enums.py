from enum import Enum


class IntentType(str, Enum):
    """模型建议的对话意图，只用于内部路由。"""

    CHAT = "CHAT"
    CONSULT = "CONSULT"
    RISK = "RISK"


class RiskLevel(str, Enum):
    """用于安全分流的风险等级，不代表医学诊断。"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
