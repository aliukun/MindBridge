import unittest

from app.ai.parsing import ModelAnalysis
from app.core.enums import IntentType, RiskLevel
from app.services.ai_risk_service import (
    HIGH_RISK_SAFE_REPLY,
    MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
    MODEL_RISK_ADVISORY_VERSION,
    merge_risk_assessment,
    risk_priority,
    select_response_intent,
)
from app.services.risk_service import PsychologicalAssessment


class AiRiskServiceTests(unittest.TestCase):
    def _hard_assessment(
        self,
        risk_level: RiskLevel,
    ) -> PsychologicalAssessment:
        return PsychologicalAssessment(
            risk_level=risk_level,
            matched_signals=(
                ("HARD_SIGNAL",) if risk_level is not RiskLevel.LOW else ()
            ),
            summary="固定硬规则摘要。",
            rule_version="keyword_rule_v1",
        )

    def _model_analysis(
        self,
        risk_level: RiskLevel,
        *,
        intent: IntentType = IntentType.CONSULT,
        summary: str = "模型原始摘要",
    ) -> ModelAnalysis:
        return ModelAnalysis(
            intent=intent,
            suggested_risk=risk_level,
            summary=summary,
        )

    def test_model_can_raise_low_to_medium_without_persisting_summary(
        self,
    ):
        private_model_summary = "模型复述了 13800138000"

        merged = merge_risk_assessment(
            self._hard_assessment(RiskLevel.LOW),
            self._model_analysis(
                RiskLevel.MEDIUM,
                summary=private_model_summary,
            ),
        )

        self.assertIs(
            merged.final_assessment.risk_level,
            RiskLevel.MEDIUM,
        )

        self.assertTrue(merged.model_raised_risk)

        self.assertNotIn(
            private_model_summary,
            merged.final_assessment.summary,
        )

        self.assertIn(
            MODEL_RISK_ADVISORY_VERSION,
            merged.final_assessment.rule_version,
        )

    def test_model_cannot_lower_hard_rule_medium(self):
        hard_assessment = self._hard_assessment(RiskLevel.MEDIUM)

        merged = merge_risk_assessment(
            hard_assessment,
            self._model_analysis(RiskLevel.LOW),
        )

        self.assertIs(
            merged.final_assessment.risk_level,
            RiskLevel.MEDIUM,
        )

        self.assertFalse(merged.model_raised_risk)

    def test_model_cannot_lower_hard_rule_high(self):
        merged = merge_risk_assessment(
            self._hard_assessment(RiskLevel.HIGH),
            self._model_analysis(RiskLevel.LOW),
        )

        self.assertIs(
            merged.final_assessment.risk_level,
            RiskLevel.HIGH,
        )

    def test_missing_model_analysis_keeps_hard_rule(self):
        hard_assessment = self._hard_assessment(RiskLevel.LOW)

        merged = merge_risk_assessment(
            hard_assessment,
            None,
        )

        self.assertEqual(
            merged.final_assessment,
            hard_assessment,
        )

        self.assertIsNone(merged.model_suggested_risk)
        self.assertFalse(merged.model_raised_risk)

    def test_risk_priority_is_monotonic(self):
        self.assertLess(
            risk_priority(RiskLevel.LOW),
            risk_priority(RiskLevel.MEDIUM),
        )

        self.assertLess(
            risk_priority(RiskLevel.MEDIUM),
            risk_priority(RiskLevel.HIGH),
        )

    def test_final_risk_overrides_response_intent(self):
        chat_analysis = self._model_analysis(
            RiskLevel.LOW,
            intent=IntentType.CHAT,
        )

        self.assertIs(
            select_response_intent(
                chat_analysis,
                RiskLevel.HIGH,
            ),
            IntentType.RISK,
        )

        self.assertIs(
            select_response_intent(
                chat_analysis,
                RiskLevel.MEDIUM,
            ),
            IntentType.CONSULT,
        )

        self.assertIs(
            select_response_intent(
                None,
                RiskLevel.LOW,
            ),
            IntentType.CHAT,
        )

    def test_fixed_fallbacks_do_not_expose_internal_labels(self):
        self.assertEqual(
            HIGH_RISK_SAFE_REPLY.count("？"),
            1,
        )

        self.assertNotIn(
            "HIGH",
            HIGH_RISK_SAFE_REPLY,
        )

        self.assertNotIn(
            "MEDIUM",
            MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
        )

        self.assertIn(
            "AI 服务暂时不可用",
            MEDIUM_PROVIDER_UNAVAILABLE_REPLY,
        )


if __name__ == "__main__":
    unittest.main()
