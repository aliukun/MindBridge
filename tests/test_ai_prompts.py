import unittest

from app.ai.contracts import AiRequestOptions, AiRole
from app.ai.prompts import (
    ANALYSIS_MAX_TOKENS,
    ANALYSIS_PROMPT_VERSION,
    REPLY_PROMPT_VERSION,
    build_analysis_request,
    build_reply_request,
)
from app.core.enums import IntentType, RiskLevel


class AiPromptTests(unittest.TestCase):
    def setUp(self):
        self.options = AiRequestOptions(
            temperature=0.35,
            max_tokens=512,
        )

    def test_analysis_request_is_low_randomness_and_strict_json(self):
        request = build_analysis_request(
            "已经脱敏的消息",
            options=self.options,
        )

        self.assertEqual(len(request.messages), 2)
        self.assertIs(request.messages[0].role, AiRole.SYSTEM)
        self.assertIs(request.messages[1].role, AiRole.USER)

        self.assertEqual(
            request.messages[1].content,
            "已经脱敏的消息",
        )

        self.assertEqual(request.options.temperature, 0.0)

        self.assertEqual(
            request.options.max_tokens,
            ANALYSIS_MAX_TOKENS,
        )

        self.assertIn(
            ANALYSIS_PROMPT_VERSION,
            request.messages[0].content,
        )

        self.assertIn(
            '"suggested_risk"',
            request.messages[0].content,
        )

        self.assertIn(
            "禁止 Markdown",
            request.messages[0].content,
        )

    def test_analysis_does_not_increase_small_token_budget(self):
        options = AiRequestOptions(
            temperature=1.0,
            max_tokens=64,
        )

        request = build_analysis_request(
            "消息",
            options=options,
        )

        self.assertEqual(request.options.max_tokens, 64)
        self.assertEqual(options.temperature, 1.0)

    def test_general_reply_keeps_injected_options(self):
        request = build_reply_request(
            "Python 函数是什么？",
            intent=IntentType.CHAT,
            final_risk=RiskLevel.LOW,
            options=self.options,
        )

        self.assertEqual(request.options, self.options)

        self.assertIn(
            REPLY_PROMPT_VERSION,
            request.messages[0].content,
        )

        self.assertIn(
            "日常陪伴",
            request.messages[0].content,
        )

    def test_consult_or_medium_uses_support_prompt(self):
        request = build_reply_request(
            "最近压力很大",
            intent=IntentType.CHAT,
            final_risk=RiskLevel.MEDIUM,
            options=self.options,
        )

        self.assertIn(
            "心理支持",
            request.messages[0].content,
        )

    def test_high_risk_cannot_build_a_model_reply(self):
        with self.assertRaisesRegex(
            ValueError,
            "deterministic safety reply",
        ):
            build_reply_request(
                "高风险消息",
                intent=IntentType.RISK,
                final_risk=RiskLevel.HIGH,
                options=self.options,
            )

    def test_blank_input_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must not be blank",
        ):
            build_analysis_request(
                "   ",
                options=self.options,
            )


if __name__ == "__main__":
    unittest.main()
