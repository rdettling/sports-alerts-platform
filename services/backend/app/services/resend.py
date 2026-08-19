from __future__ import annotations

import json
from dataclasses import dataclass
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.services.api_usage import record_api_call_event
from app.services.delivery_settings import delivery_settings


@dataclass(frozen=True)
class ResendResult:
    sent: bool
    provider_message_id: str | None = None
    metadata: dict[str, object] | None = None


def _record_attempt(
    db: Session | None,
    *,
    service: str,
    attempt_status: str,
    started_at: float,
    http_status: int | None = None,
    error_code: str | None = None,
) -> None:
    if db is None:
        return
    record_api_call_event(
        db,
        service=service,
        provider="resend",
        endpoint_key="resend_send_email",
        attempt_status=attempt_status,
        http_status=http_status,
        latency_ms=int((monotonic() - started_at) * 1000),
        error_code=error_code,
    )


def send_resend_email(
    db: Session | None,
    *,
    service: str,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> ResendResult:
    if not delivery_settings.resend_api_key:
        return ResendResult(sent=False, metadata={"error": "missing_resend_api_key"})

    payload = json.dumps(
        {
            "from": delivery_settings.from_email,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    ).encode("utf-8")
    request = Request(
        delivery_settings.resend_api_url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {delivery_settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "sports-alerts-api/1.0",
        },
    )
    started_at = monotonic()
    try:
        with urlopen(request, timeout=15.0) as response:
            status_code = int(getattr(response, "status", 200))
            response_body = response.read().decode("utf-8")
            sent = 200 <= status_code < 300
            _record_attempt(
                db,
                service=service,
                attempt_status="rate_limited" if status_code == 429 else ("success" if sent else "error"),
                started_at=started_at,
                http_status=status_code,
                error_code=None if sent else "resend_request_failed",
            )
            if not sent:
                return ResendResult(
                    sent=False,
                    metadata={
                        "error": "resend_request_failed",
                        "status_code": status_code,
                        "response_body": response_body[:500],
                    },
                )
            try:
                provider_id = json.loads(response_body).get("id")
            except json.JSONDecodeError:
                provider_id = None
            if isinstance(provider_id, str) and provider_id:
                return ResendResult(sent=True, provider_message_id=provider_id)
            return ResendResult(sent=True, metadata={"provider_warning": "missing_message_id"})
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        _record_attempt(
            db,
            service=service,
            attempt_status="rate_limited" if exc.code == 429 else "error",
            started_at=started_at,
            http_status=exc.code,
            error_code="resend_request_failed",
        )
        return ResendResult(
            sent=False,
            metadata={
                "error": "resend_request_failed",
                "status_code": exc.code,
                "response_body": response_body[:500],
            },
        )
    except URLError as exc:
        _record_attempt(
            db,
            service=service,
            attempt_status="error",
            started_at=started_at,
            error_code="resend_http_error",
        )
        return ResendResult(
            sent=False,
            metadata={"error": "resend_http_error", "detail": str(exc.reason)},
        )
