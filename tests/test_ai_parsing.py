import unittest

from app.ai.parsing import (
    MAX_MODEL_ANALYSIS_SUMMARY_LENGTH,
    ModelAnalysisParseError,
    parse_model_analysis,
)
from app.core.enums import IntentType, RiskLevel

VALID_JSON = (
    '{"intent":"CONSULT","suggested_risk":"MEDIUM","summary":"需要更多现实支持"}'
)


class AiParsingTests(unittest.TestCase):
    def test_pure_json_is_parsed_and_summary_is_normalized(self):
        result = parse_model_analysis(
            '{"intent":"CHAT","suggested_risk":"LOW","summary":"  ordinary request  "}'
        )

        self.assertIs(result.intent, IntentType.CHAT)
        self.assertIs(
            result.suggested_risk,
            RiskLevel.LOW,
        )
        self.assertEqual(
            result.summary,
            "ordinary request",
        )

    def test_complete_json_fence_is_accepted(self):
        for fence in (
            f"```json\n{VALID_JSON}\n```",
            f"```\n{VALID_JSON}\n```",
            f"```JSON\r\n{VALID_JSON}\r\n```",
        ):
            with self.subTest(fence=fence[:10]):
                result = parse_model_analysis(fence)

                self.assertIs(
                    result.intent,
                    IntentType.CONSULT,
                )

    def test_prose_partial_fences_and_wrong_schema_are_rejected(self):
        invalid_results = (
            f"Here is the result: {VALID_JSON}",
            f"prefix\n```json\n{VALID_JSON}\n```",
            f"```python\n{VALID_JSON}\n```",
            '[{"intent":"CHAT"}]',
            ('{"intent":"UNKNOWN","suggested_risk":"LOW","summary":"x"}'),
            ('{"intent":"CHAT","suggested_risk":"low","summary":"x"}'),
            ('{"intent":"CHAT","suggested_risk":"LOW","summary":"x","extra":true}'),
            ('{"intent":"CHAT","suggested_risk":"LOW","summary":"   "}'),
            ('{"intent":"CHAT","suggested_risk":"LOW","summary":NaN}'),
        )

        for raw_result in invalid_results:
            with self.subTest(raw_result=raw_result[:30]):
                with self.assertRaises(ModelAnalysisParseError):
                    parse_model_analysis(raw_result)

    def test_overlong_summary_is_rejected(self):
        overlong_summary = "x" * (MAX_MODEL_ANALYSIS_SUMMARY_LENGTH + 1)

        raw_result = (
            f'{{"intent":"CHAT","suggested_risk":"LOW","summary":"{overlong_summary}"}}'
        )

        with self.assertRaises(ModelAnalysisParseError):
            parse_model_analysis(raw_result)

    def test_parse_error_never_echoes_raw_model_output(self):
        private_value = "13800138000"

        with self.assertRaises(ModelAnalysisParseError) as raised:
            parse_model_analysis(f"not-json-{private_value}")

        self.assertNotIn(
            private_value,
            str(raised.exception),
        )


if __name__ == "__main__":
    unittest.main()
