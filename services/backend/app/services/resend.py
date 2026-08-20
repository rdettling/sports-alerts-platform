from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.delivery_settings import delivery_settings


@dataclass(frozen=True)
class ResendResult:
    sent: bool
    provider_message_id: str | None = None
    metadata: dict[str, object] | None = None


def send_resend_email(
    *,
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
    try:
        with urlopen(request, timeout=15.0) as response:
            status_code = int(getattr(response, "status", 200))
            response_body = response.read().decode("utf-8")
            sent = 200 <= status_code < 300
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
        return ResendResult(
            sent=False,
            metadata={
                "error": "resend_request_failed",
                "status_code": exc.code,
                "response_body": response_body[:500],
            },
        )
    except URLError as exc:
        return ResendResult(
            sent=False,
            metadata={"error": "resend_http_error", "detail": str(exc.reason)},
        )
