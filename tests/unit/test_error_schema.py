"""Unit tests for IS-03 error response schema.

Verifies:
- Error responses have the correct shape.
- machine-readable codes are strings.
- retryable flag is a boolean.
- correlation_id is present.
- No stack traces in responses.
- API error handler returns correct shapes.
"""

import pytest

from sceneforge.schemas.errors import ErrorResponse, make_error_response
from sceneforge.schemas.exceptions import (
    EmptyScriptError,
    IdempotencyConflictError,
    MediaProviderUnavailableError,
    NotFoundError,
    SceneForgeError,
)


class TestErrorResponseShape:
    def test_make_error_response_structure(self):
        resp = make_error_response(
            code="TEST_ERROR",
            message="Something went wrong.",
            retryable=True,
            correlation_id="cid-123",
            details={"key": "value"},
        )
        assert isinstance(resp, ErrorResponse)
        d = resp.error
        assert d.code == "TEST_ERROR"
        assert d.message == "Something went wrong."
        assert d.retryable is True
        assert d.correlation_id == "cid-123"
        assert d.details == {"key": "value"}

    def test_model_dump_has_error_key(self):
        resp = make_error_response(
            code="FOO", message="bar", retryable=False
        )
        dumped = resp.model_dump()
        assert "error" in dumped
        assert "code" in dumped["error"]
        assert "message" in dumped["error"]
        assert "retryable" in dumped["error"]
        assert "correlation_id" in dumped["error"]
        assert "details" in dumped["error"]

    def test_code_is_string(self):
        resp = make_error_response(code="MY_CODE", message="msg", retryable=False)
        assert isinstance(resp.error.code, str)

    def test_retryable_is_bool(self):
        r1 = make_error_response(code="A", message="m", retryable=True)
        r2 = make_error_response(code="B", message="m", retryable=False)
        assert r1.error.retryable is True
        assert r2.error.retryable is False

    def test_default_details_empty_dict(self):
        resp = make_error_response(code="X", message="m", retryable=False)
        assert resp.error.details == {}

    def test_default_correlation_id_empty_string(self):
        resp = make_error_response(code="X", message="m", retryable=False)
        assert resp.error.correlation_id == ""


class TestDomainExceptions:
    def test_empty_script_error(self):
        exc = EmptyScriptError()
        assert exc.code == "EMPTY_SCRIPT"
        assert exc.retryable is False
        assert exc.http_status == 422

    def test_not_found_error(self):
        exc = NotFoundError("Job")
        assert exc.code == "NOT_FOUND"
        assert exc.http_status == 404
        assert exc.retryable is False

    def test_idempotency_conflict_error(self):
        exc = IdempotencyConflictError()
        assert exc.code == "IDEMPOTENCY_CONFLICT"
        assert exc.http_status == 409
        assert exc.retryable is False

    def test_media_provider_unavailable_retryable(self):
        exc = MediaProviderUnavailableError("pexels")
        assert exc.code == "MEDIA_PROVIDER_UNAVAILABLE"
        assert exc.retryable is True
        assert exc.http_status == 502

    def test_all_sceneforge_errors_have_required_attrs(self):
        exceptions = [
            EmptyScriptError(),
            NotFoundError(),
            IdempotencyConflictError(),
            MediaProviderUnavailableError(),
        ]
        for exc in exceptions:
            assert isinstance(exc.code, str)
            assert exc.code == exc.code.upper()  # SCREAMING_SNAKE_CASE
            assert isinstance(exc.retryable, bool)
            assert isinstance(exc.http_status, int)
            assert isinstance(exc.message, str)
            # No internal paths or stack trace content in message
            assert "traceback" not in exc.message.lower()
            assert "sqlalchemy" not in exc.message.lower()


class TestAPIErrorHandlerIntegration:
    """Integration tests: API returns IS-03 shape for errors."""

    def test_not_found_returns_error_shape(self, api_client):
        """GET /jobs/{unknown} returns 404 with IS-03 shape."""
        import uuid
        resp = api_client.get(f"/jobs/{uuid.uuid4()}")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "NOT_FOUND"
        assert isinstance(body["error"]["retryable"], bool)
        assert "correlation_id" in body["error"]

    def test_validation_error_returns_error_shape(self, api_client):
        """POST /jobs with invalid aspect_ratio returns 422 with IS-03 shape."""
        resp = api_client.post(
            "/jobs",
            json={"script": "test", "aspect_ratio": "invalid"},
            headers={"Idempotency-Key": "test-key-validation"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_no_stack_trace_in_error_response(self, api_client):
        """Error responses must not contain Python tracebacks."""
        import uuid
        resp = api_client.get(f"/jobs/{uuid.uuid4()}")
        body_str = resp.text
        assert "Traceback" not in body_str
        assert "File " not in body_str
        assert "sqlalchemy" not in body_str.lower()
