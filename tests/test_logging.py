import io
import logging
import unittest
from unittest.mock import patch

from pydantic import SecretStr

from app.core.config import Settings
from app.core.logging import (
    REDACTED,
    SafeFormatter,
    configure_logging,
)


class SafeLoggingTests(unittest.TestCase):
    def build_capture_logger(
        self,
        *,
        secret_values: tuple[str, ...] = (),
    ) -> tuple[
        logging.Logger,
        io.StringIO,
        logging.Handler,
    ]:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)

        handler.setFormatter(
            SafeFormatter(
                fmt="%(levelname)s %(message)s",
                secret_values=secret_values,
            )
        )

        logger = logging.Logger(f"safe-logging-test-{id(stream)}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.addHandler(handler)

        return logger, stream, handler

    def test_credentials_and_known_secrets_are_redacted(
        self,
    ):
        known_secret = "known-bootstrap-password-2026"

        logger, stream, handler = self.build_capture_logger(
            secret_values=(known_secret,),
        )

        try:
            logger.error(
                (
                    "headers=%r password=%s "
                    "api_key=%s bearer=%s "
                    "database=%s config=%r bare=%s"
                ),
                {
                    "Authorization": ("Basic basic-token-123"),
                },
                "request-password-456",
                "api-key-789",
                "Bearer bearer-token-987",
                ("mysql+pymysql://student:database-password@localhost/mindbridge"),
                SecretStr(known_secret),
                known_secret,
            )
        finally:
            handler.flush()
            logger.removeHandler(handler)
            handler.close()

        output = stream.getvalue()

        for secret in (
            "basic-token-123",
            "request-password-456",
            "api-key-789",
            "bearer-token-987",
            "database-password",
            known_secret,
        ):
            self.assertNotIn(secret, output)

        self.assertIn(REDACTED, output)
        self.assertIn("student:", output)
        self.assertIn("@localhost", output)

    def test_exception_keeps_type_and_position_not_message(
        self,
    ):
        logger, stream, handler = self.build_capture_logger()

        sensitive_message = "complete private user message"

        try:
            try:
                raise RuntimeError(sensitive_message)
            except RuntimeError:
                logger.exception(("request failed exception_type=RuntimeError"))
        finally:
            handler.flush()
            logger.removeHandler(handler)
            handler.close()

        output = stream.getvalue()

        self.assertNotIn(
            sensitive_message,
            output,
        )
        self.assertIn("RuntimeError", output)
        self.assertIn("test_logging.py", output)
        self.assertIn("line", output)

    def test_safe_context_remains_readable(self):
        logger, stream, handler = self.build_capture_logger()

        try:
            logger.info(
                ("request_id=%s method=%s route=%s status_code=%s"),
                "request-123",
                "POST",
                "/api/chat/sessions/{public_id}",
                201,
            )
        finally:
            handler.flush()
            logger.removeHandler(handler)
            handler.close()

        output = stream.getvalue()

        self.assertIn(
            "request_id=request-123",
            output,
        )
        self.assertIn("method=POST", output)
        self.assertIn("status_code=201", output)

    def test_repeated_configuration_does_not_add_handlers(
        self,
    ):
        settings = Settings(_env_file=None)
        isolated_logger = logging.Logger("isolated-app-logger")

        with patch(
            "app.core.logging.logging.getLogger",
            return_value=isolated_logger,
        ):
            configure_logging(settings)
            configure_logging(settings)

        safe_handlers = [
            handler
            for handler in isolated_logger.handlers
            if getattr(
                handler,
                "_mindbridge_safe_handler",
                False,
            )
        ]

        try:
            self.assertEqual(
                len(safe_handlers),
                1,
            )
        finally:
            for handler in safe_handlers:
                isolated_logger.removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    unittest.main()
