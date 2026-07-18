from enum import Enum


class RiskLevel(str, Enum):
    """用于安全分流的风险等级，不代表医学诊断"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
