from starlette.requests import Request

from error_handler import ErrorHandler, REDACTED


def _request(headers=None, path="/api/v1/protected", query_string=b"access_token=secret-token"):
    raw_headers = []
    for name, value in (headers or {}).items():
        raw_headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
    return Request({
        "type": "http",
        "method": "GET",
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
