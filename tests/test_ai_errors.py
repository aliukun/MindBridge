import unittest

from app.ai.errors import (
    AiAuthenticationError,
    AiConfigurationError,
    AiError,
    AiModelNotFoundError,
    AiProtocolError,
    AiProviderError,
    AiRateLimitError,
    AiResponseError,
    AiTimeoutError,
    AiUnavailableError,
)


class AiErrorTests(unittest.TestCase):
    def test_provider_errors_share_stable_parent_types(self):
        provider_errors = (
            AiUnavailableError("unavailable"),
            AiTimeoutError("timeout"),
            AiAuthenticationError("authentication"),
            AiModelNotFoundError("model"),
            AiRateLimitError("rate-limit"),
            AiResponseError("response"),
            AiProtocolError("protocol"),
        )

        for error in provider_errors:
            with self.subTest(error_type=type(error).__name__):
                self.assertIsInstance(
                    error,
                    AiProviderError,
                )
                self.assertIsInstance(
                    error,
                    AiError,
                )

    def test_configuration_error_is_not_provider_failure(self):
        error = AiConfigurationError(
            "configuration",
        )

        self.assertIsInstance(error, AiError)
        self.assertNotIsInstance(
            error,
            AiProviderError,
        )


if __name__ == "__main__":
    unittest.main()
