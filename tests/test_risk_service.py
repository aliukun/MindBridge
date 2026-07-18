import unittest

from app.core.enums import RiskLevel
from app.services.risk_service import (
    NON_DIAGNOSTIC_DISCLAIMER,
    RISK_RULE_VERSION,
    assess_psychological_risk,
)


class RiskServiceTests(unittest.TestCase):
    def test_ordinary_stress_is_low(self):
        result = assess_psychological_risk("这周考试有点紧张。")

        self.assertEqual(
            result.risk_level,
            RiskLevel.LOW,
        )

        self.assertFalse(result.needs_support)

        self.assertFalse(result.immediate_support)

        self.assertEqual(
            result.matched_signals,
            (),
        )

    def test_persistent_distress_is_medium(self):
        result = assess_psychological_risk("我连续失眠，已经无法正常生活。")

        self.assertEqual(
            result.risk_level,
            RiskLevel.MEDIUM,
        )

        self.assertTrue(result.needs_support)

        self.assertFalse(result.immediate_support)

        self.assertIn(
            "FUNCTIONAL_IMPAIRMENT",
            result.matched_signals,
        )

    def test_explicit_self_harm_signal_is_high(self):
        result = assess_psychological_risk("我不想活了，也想伤害自己。")

        self.assertEqual(
            result.risk_level,
            RiskLevel.HIGH,
        )

        self.assertTrue(result.immediate_support)

        self.assertIn(
            "SELF_HARM_OR_SUICIDE",
            result.matched_signals,
        )

        self.assertEqual(
            result.rule_version,
            RISK_RULE_VERSION,
        )

    def test_english_matching_normalizes_width_and_case(
        self,
    ):
        result = assess_psychological_risk("Ｉ ＷＡＮＴ ＴＯ ＤＩＥ。")

        self.assertEqual(
            result.risk_level,
            RiskLevel.HIGH,
        )

    def test_high_rule_has_priority_over_medium_rule(
        self,
    ):
        result = assess_psychological_risk("我长期失眠，而且现在不想活了。")

        self.assertEqual(
            result.risk_level,
            RiskLevel.HIGH,
        )

    def test_blank_text_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_psychological_risk("   ")

    def test_high_result_is_non_diagnostic_backend_metadata(
        self,
    ):
        result = assess_psychological_risk("我想伤害自己。")

        self.assertIn(
            "安全确认",
            result.summary,
        )

        self.assertIn(
            "不是临床诊断",
            result.summary,
        )

        self.assertIn(
            "不是医学或心理诊断",
            NON_DIAGNOSTIC_DISCLAIMER,
        )


if __name__ == "__main__":
    unittest.main()
