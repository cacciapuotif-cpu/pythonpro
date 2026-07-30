import asyncio
import logging

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.requests import Request

from error_handler import ErrorHandler, REDACTED
from main import sanitize_body_for_log, validation_exception_handler
from routers.auth import PasswordResetConfirm


def _request(
    headers=None,
    path="/api/v1/protected",
    query_string=b"access_token=secret-token",
    method="GET",
):
    raw_headers = []
    for name, value in (headers or {}).items():
        raw_headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string,
        "headers": raw_headers,
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
    })


def test_log_error_redacts_sensitive_headers_and_query_string():
    request = _request({
        "Authorization": "Bearer live-token-value",
        "Cookie": "sessionid=secret-cookie",
        "X-Request-ID": "req-123",
        "User-Agent": "browser fingerprint",
    })

    try:
        raise RuntimeError("failure token=secret-token password=secret-password")
    except RuntimeError as exc:
        error_info = ErrorHandler.log_error(exc, request, user_id=42)

    rendered = str(error_info)
    assert "live-token-value" not in rendered
    assert "secret-cookie" not in rendered
    assert "secret-token" not in rendered
    assert "secret-password" not in rendered
    assert "browser fingerprint" not in rendered
    assert "access_token" not in rendered
    assert error_info["request_path"] == "/api/v1/protected"
    assert error_info["request_headers"]["authorization"] == REDACTED
    assert error_info["request_headers"]["cookie"] == REDACTED
    assert error_info["request_headers"]["x-request-id"] == "req-123"


def test_redact_text_covers_common_secret_patterns():
    text = ErrorHandler.redact_text(
        "Authorization: Bearer abc.def token=my-token api_key=my-key password=my-password"
    )

    assert "abc.def" not in text
    assert "my-token" not in text
    assert "my-key" not in text
    assert "my-password" not in text
    assert text.count(REDACTED) >= 4


def test_profile_validation_body_redacts_name_email_and_password():
    sanitized = sanitize_body_for_log({
        "full_name": "Mario Rossi",
        "email": "mario@example.com",
        "new_password": "SecretPassword123!",
    })

    assert sanitized == {
        "full_name": "***REDACTED***",
        "email": "***REDACTED***",
        "new_password": "***REDACTED***",
    }


def test_auth_validation_error_never_logs_password_or_reset_token(caplog):
    leaked_password = "lowercase-secret1!"
    leaked_token = "reset-token-that-must-never-reach-logs"

    try:
        PasswordResetConfirm.model_validate(
            {
                "token": leaked_token,
                "new_password": leaked_password,
                "confirm_password": leaked_password,
            }
        )
    except PydanticValidationError as exc:
        request_error = RequestValidationError(exc.errors())
    else:  # pragma: no cover - il payload deve essere intenzionalmente invalido
        raise AssertionError("Il payload debole doveva produrre un errore di validazione")

    with caplog.at_level(logging.ERROR):
        response = asyncio.run(
            validation_exception_handler(
                _request(path="/api/v1/auth/reset-password", query_string=b"", method="POST"),
                request_error,
            )
        )

    assert response.status_code == 422
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert leaked_password not in rendered_logs
    assert leaked_token not in rendered_logs
    assert "new_password" not in rendered_logs
    assert "reset-password" in rendered_logs
