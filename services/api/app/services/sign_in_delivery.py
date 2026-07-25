from __future__ import annotations

import json
import logging
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.config import settings
from app.services.api_usage import record_api_call_event
from app.services.delivery_settings import delivery_settings
from app.services.email_templates import build_sign_in_email

logger = logging.getLogger(__name__)


def send_sign_in_email(
    to_email: str,
    magic_link: str,
    magic_code: str,
    db: Session | None = None,
) -> None:
    subject, text_body, html_body = build_sign_in_email(
        magic_link,
        magic_code,
        settings.magic_link_ttl_minutes,
    )

    if delivery_settings.delivery_mode == "log":
        logger.info(
            "Sign-in email to=%s subject=%s code=%s link=%s",
            to_email,
            subject,
            magic_code,
            magic_link,
        )
        return

    if delivery_settings.delivery_mode != "live":
        logger.warning("Unsupported delivery mode=%s while sending sign-in email", delivery_settings.delivery_mode)
        return

    if not delivery_settings.resend_api_key:
        logger.warning("Missing RESEND_API_KEY while sending sign-in email to=%s", to_email)
        return

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
            if db is not None:
                record_api_call_event(
                    db,
                    service="api",
                    provider="resend",
                    endpoint_key="resend_send_email",
                    attempt_status="rate_limited" if status_code == 429 else ("success" if 200 <= status_code < 300 else "error"),
                    http_status=status_code,
                    latency_ms=int((monotonic() - started_at) * 1000),
                )
            if response.status >= 400:
                logger.warning("Resend rejected sign-in email status=%s", response.status)
    except HTTPError as exc:
        if db is not None:
            record_api_call_event(
                db,
                service="api",
                provider="resend",
                endpoint_key="resend_send_email",
                attempt_status="rate_limited" if exc.code == 429 else "error",
                http_status=exc.code,
                latency_ms=int((monotonic() - started_at) * 1000),
                error_code="http_error",
            )
        logger.warning("Resend HTTP error delivering sign-in email status=%s", exc.code)
    except URLError as exc:
        if db is not None:
            record_api_call_event(
                db,
                service="api",
                provider="resend",
                endpoint_key="resend_send_email",
                attempt_status="error",
                latency_ms=int((monotonic() - started_at) * 1000),
                error_code="network_error",
            )
        logger.warning("Resend network error delivering sign-in email error=%s", exc.reason)
