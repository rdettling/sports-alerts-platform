import logging

from app.logging_filters import SuppressLowSignalAccessLogsFilter


def _access_record(method: str, path: str) -> logging.LogRecord:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:12345", method, path, "1.1", 200),
        exc_info=None,
    )
    return record


def _rendered_access_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_access_log_filter_suppresses_health_checks():
    log_filter = SuppressLowSignalAccessLogsFilter()
    assert log_filter.filter(_access_record("GET", "/healthz")) is False


def test_access_log_filter_suppresses_preflight_requests():
    log_filter = SuppressLowSignalAccessLogsFilter()
    assert log_filter.filter(_access_record("OPTIONS", "/games?include_finals=true&limit=200")) is False


def test_access_log_filter_keeps_application_requests():
    log_filter = SuppressLowSignalAccessLogsFilter()
    assert log_filter.filter(_access_record("GET", "/ops/admin/overview?window=24h&limit=30")) is True


def test_access_log_filter_suppresses_rendered_health_check_message():
    log_filter = SuppressLowSignalAccessLogsFilter()
    assert log_filter.filter(_rendered_access_record('127.0.0.1:33058 - "GET /healthz HTTP/1.1" 200 OK')) is False


def test_access_log_filter_keeps_rendered_application_message():
    log_filter = SuppressLowSignalAccessLogsFilter()
    assert (
        log_filter.filter(
            _rendered_access_record('172.18.0.1:64932 - "GET /games?include_finals=true&limit=200 HTTP/1.1" 200 OK')
        )
        is True
    )
