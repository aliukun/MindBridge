import re
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    REQUEST_ID_HEADER,
    AppError,
    ErrorCode,
    RequestIdMiddleware,
    register_exception_handlers,
)


class NumberPayload(BaseModel):
    number: int


def build_error_test_app() -> FastAPI:
    application = FastAPI()

    application.add_middleware(RequestIdMiddleware)

    register_exception_handlers(application)

    @application.get("/success")
    def return_success() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/app-error")
    def raise_app_error() -> None:
        raise AppError(
            status_code=409,
            code=ErrorCode.CONFLICT,
            detail="A public conflict occurred.",
        )

    @application.get("/unauthorized")
    def raise_http_error() -> None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={
                "WWW-Authenticate": ('Basic realm="MindBridge"'),
            },
        )

    @application.post("/validate")
    def validate_payload(
        payload: NumberPayload,
    ) -> NumberPayload:
        return payload

    @application.get("/unexpected")
    def raise_unexpected_error() -> None:
        sensitive_message = "complete-sensitive-message"

        raise RuntimeError(sensitive_message)

    return application


class ErrorResponseTests(unittest.TestCase):
    def setUp(self):
        self.application = build_error_test_app()
        self.client = TestClient(
            self.application,
            raise_server_exceptions=False,
        )

    def tearDown(self):
        self.client.close()

    def test_app_error_has_stable_public_shape(self):
        response = self.client.get(
            "/app-error",
            headers={
                REQUEST_ID_HEADER: ("safe-request_2026.07"),
            },
        )

        self.assertEqual(response.status_code, 409)

        body = response.json()

        self.assertEqual(
            body,
            {
                "code": "conflict",
                "detail": ("A public conflict occurred."),
                "request_id": ("safe-request_2026.07"),
            },
        )

        self.assertEqual(
            response.headers[REQUEST_ID_HEADER],
            body["request_id"],
        )

    def test_http_exception_keeps_detail_and_headers(
        self,
    ):
        response = self.client.get("/unauthorized")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"],
            "Authentication required.",
        )
        self.assertEqual(
            response.json()["code"],
            "unauthorized",
        )
        self.assertIn(
            "Basic",
            response.headers["WWW-Authenticate"],
        )

    def test_framework_not_found_is_also_stable(self):
        response = self.client.get("/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["code"],
            "not_found",
        )
        self.assertEqual(
            response.json()["detail"],
            "Not Found",
        )
        self.assertEqual(
            response.headers[REQUEST_ID_HEADER],
            response.json()["request_id"],
        )

    def test_validation_error_does_not_echo_input_or_ctx(
        self,
    ):
        sensitive_input = "complete-sensitive-validation-input"

        response = self.client.post(
            "/validate",
            json={
                "number": sensitive_input,
            },
        )

        self.assertEqual(response.status_code, 422)

        body = response.json()

        self.assertEqual(
            body["code"],
            "validation_error",
        )
        self.assertNotIn(
            sensitive_input,
            response.text,
        )

        for error in body["detail"]:
            self.assertEqual(
                set(error),
                {"type", "loc", "msg"},
            )
            self.assertNotIn("input", error)
            self.assertNotIn("ctx", error)

    def test_unexpected_error_returns_fixed_safe_response(
        self,
    ):
        with patch("app.core.errors.logger.error") as log_error:
            response = self.client.get("/unexpected")

        self.assertEqual(response.status_code, 500)

        body = response.json()

        self.assertEqual(
            body["code"],
            "internal_error",
        )
        self.assertEqual(
            body["detail"],
            "Internal server error.",
        )
        self.assertNotIn(
            "complete-sensitive-message",
            response.text,
        )
        self.assertNotIn(
            "RuntimeError",
            response.text,
        )
        self.assertEqual(
            response.headers[REQUEST_ID_HEADER],
            body["request_id"],
        )

        log_error.assert_called_once()
        self.assertIn(
            "exc_info",
            log_error.call_args.kwargs,
        )

    def test_unsafe_request_id_is_replaced(self):
        unsafe_request_id = "x" * 65

        response = self.client.get(
            "/missing",
            headers={
                REQUEST_ID_HEADER: unsafe_request_id,
            },
        )

        request_id = response.json()["request_id"]

        self.assertNotEqual(
            request_id,
            unsafe_request_id,
        )
        self.assertIsNotNone(
            re.fullmatch(
                r"[0-9a-f]{32}",
                request_id,
            )
        )

    def test_success_response_reuses_safe_request_id(
        self,
    ):
        response = self.client.get(
            "/success",
            headers={
                REQUEST_ID_HEADER: ("safe-success-request"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers[REQUEST_ID_HEADER],
            "safe-success-request",
        )

    def test_success_response_replaces_unsafe_request_id(
        self,
    ):
        response = self.client.get(
            "/success",
            headers={
                REQUEST_ID_HEADER: "x" * 65,
            },
        )

        request_id = response.headers[REQUEST_ID_HEADER]

        self.assertIsNotNone(
            re.fullmatch(
                r"[0-9a-f]{32}",
                request_id,
            )
        )

    def test_generated_request_ids_are_unique(self):
        first = self.client.get("/missing")
        second = self.client.get("/missing")

        self.assertNotEqual(
            first.json()["request_id"],
            second.json()["request_id"],
        )

    def test_default_test_client_still_raises_server_error(
        self,
    ):
        client = TestClient(self.application)

        try:
            with patch("app.core.errors.logger.error"):
                with self.assertRaises(RuntimeError):
                    client.get("/unexpected")
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
