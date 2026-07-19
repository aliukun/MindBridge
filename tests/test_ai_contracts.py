import unittest

from pydantic import ValidationError

from app.ai.contracts import (
    MAX_AI_COMPLETION_LENGTH,
    MAX_AI_MESSAGES,
    MAX_AI_TOKENS,
    AiCompletion,
    AiFinishReason,
    AiMessage,
    AiRequest,
    AiRequestOptions,
    AiRole,
    AiStreamChunk,
    ProviderState,
)


class AiContractTests(unittest.TestCase):
    def test_ai_message_accepts_supported_roles_and_preserves_content(
        self,
    ):
        messages = [
            AiMessage(
                role=role,
                content="  keep this layout  ",
            )
            for role in (
                "system",
                "user",
                "assistant",
            )
        ]

        self.assertEqual(
            [message.role for message in messages],
            [
                AiRole.SYSTEM,
                AiRole.USER,
                AiRole.ASSISTANT,
            ],
        )
        self.assertEqual(
            messages[0].content,
            "  keep this layout  ",
        )

    def test_ai_message_rejects_unknown_role(self):
        with self.assertRaises(ValidationError):
            AiMessage(
                role="developer",
                content="Unsupported role",
            )

    def test_ai_message_rejects_blank_content(self):
        with self.assertRaises(ValidationError):
            AiMessage(
                role="user",
                content="   ",
            )

    def test_ai_message_rejects_extra_fields(self):
        with self.assertRaises(ValidationError):
            AiMessage.model_validate(
                {
                    "role": "user",
                    "content": "Hello",
                    "unexpected": True,
                }
            )

    def test_ai_message_is_frozen(self):
        message = AiMessage(
            role="user",
            content="Original",
        )

        with self.assertRaises(ValidationError):
            setattr(
                message,
                "content",
                "Changed",
            )

    def test_request_options_accept_boundaries(self):
        minimum = AiRequestOptions(
            temperature=0.0,
            max_tokens=1,
        )
        maximum = AiRequestOptions(
            temperature=2.0,
            max_tokens=MAX_AI_TOKENS,
        )

        self.assertEqual(minimum.max_tokens, 1)
        self.assertEqual(
            maximum.max_tokens,
            MAX_AI_TOKENS,
        )

    def test_request_options_reject_invalid_values(self):
        invalid_payloads = (
            {
                "temperature": -0.1,
            },
            {
                "temperature": 2.1,
            },
            {
                "temperature": float("nan"),
            },
            {
                "temperature": True,
            },
            {
                "max_tokens": 0,
            },
            {
                "max_tokens": MAX_AI_TOKENS + 1,
            },
            {
                "max_tokens": True,
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    AiRequestOptions.model_validate(payload)

    def test_ai_request_rejects_empty_or_too_many_messages(
        self,
    ):
        message = AiMessage(
            role="user",
            content="Hello",
        )

        invalid_message_sets = (
            (),
            (message,) * (MAX_AI_MESSAGES + 1),
        )

        for messages in invalid_message_sets:
            with self.subTest(message_count=len(messages)):
                with self.assertRaises(ValidationError):
                    AiRequest(
                        messages=messages,
                    )

    def test_completion_rejects_blank_text(self):
        with self.assertRaises(ValidationError):
            AiCompletion(
                text="   ",
                provider="mock",
                model="mock-model",
                finish_reason=AiFinishReason.STOP,
            )

        with self.assertRaises(ValidationError):
            AiCompletion(
                text="x" * (MAX_AI_COMPLETION_LENGTH + 1),
                provider="mock",
                model="mock-model",
                finish_reason=AiFinishReason.STOP,
            )

    def test_provider_state_distinguishes_missing_model(self):
        self.assertEqual(
            ProviderState.MODEL_NOT_FOUND.value,
            "MODEL_NOT_FOUND",
        )

    def test_stream_chunk_enforces_terminal_state(self):
        data_chunk = AiStreamChunk(
            index=0,
            delta="hello",
        )
        terminal_chunk = AiStreamChunk(
            index=1,
            done=True,
            finish_reason=AiFinishReason.STOP,
        )

        self.assertFalse(data_chunk.done)
        self.assertTrue(terminal_chunk.done)

        invalid_payloads = (
            {
                "index": 0,
                "delta": "",
                "done": False,
            },
            {
                "index": 0,
                "done": True,
            },
            {
                "index": 0,
                "delta": "text",
                "done": False,
                "finish_reason": "stop",
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    AiStreamChunk.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
