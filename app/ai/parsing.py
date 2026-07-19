import json
import re
from typing import NoReturn

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from app.core.enums import IntentType, RiskLevel

MAX_MODEL_ANALYSIS_SUMMARY_LENGTH = 300

_JSON_FENCE_PATTERN = re.compile(
    (
        r"\A```(?:json)?[ \t]*\r?\n"
        r"(?P<payload>[\s\S]*?)"
        r"\r?\n```[ \t]*\Z"
    ),
    re.IGNORECASE,
)


class ModelAnalysisParseError(ValueError):
    """模型分析结果不是允许的严格 JSON。"""


class ModelAnalysis(BaseModel):
    """模型给出的内部建议；它不能覆盖风险硬规则。"""

    intent: IntentType

    suggested_risk: RiskLevel

    summary: str = Field(
        min_length=1,
        max_length=MAX_MODEL_ANALYSIS_SUMMARY_LENGTH,
        strict=True,
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    @field_validator("summary")
    @classmethod
    def normalize_summary(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Model analysis summary must not be blank.")

        return normalized


def _reject_nonstandard_json_constant(
    value: str,
) -> NoReturn:
    raise ValueError(f"Non-standard JSON constant is not allowed: {value}.")


def _extract_json_text(text: str) -> str:
    normalized = text.strip()

    if not normalized:
        raise ModelAnalysisParseError("Model analysis was empty.") from None

    fence_match = _JSON_FENCE_PATTERN.fullmatch(normalized)

    if fence_match is not None:
        return fence_match.group("payload").strip()

    if normalized.startswith("```") or normalized.endswith("```"):
        raise ModelAnalysisParseError(
            "Model analysis used an invalid JSON fence."
        ) from None

    return normalized


def parse_model_analysis(text: str) -> ModelAnalysis:
    """只接受纯 JSON object 或完整包裹它的单一 JSON 围栏。"""

    json_text = _extract_json_text(text)

    try:
        payload = json.loads(
            json_text,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except ValueError:
        raise ModelAnalysisParseError("Model analysis was not valid JSON.") from None

    if not isinstance(payload, dict):
        raise ModelAnalysisParseError("Model analysis must be a JSON object.") from None

    try:
        return ModelAnalysis.model_validate(payload)
    except ValidationError:
        raise ModelAnalysisParseError(
            "Model analysis did not satisfy the required schema."
        ) from None
