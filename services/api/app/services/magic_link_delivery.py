from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings

logger = logging.getLogger(__name__)


def send_magic_link_email(to_email: str, magic_link: str) -> None:
    subject = "[Sports Alerts] Your sign-in link"
    text_body = (
        "Use this one-time link to sign in:\n\n"
        f"{magic_link}\n\n"
        f"This link expires in {settings.magic_link_ttl_minutes} minutes."
    )
    html_body = (
        "<!doctype html><html><body style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;\">"
        "<h2>Sports Alerts sign in</h2>"
        f"<p><a href=\"{magic_link}\">Click here to sign in</a></p>"
        f"<p>This link expires in {settings.magic_link_ttl_minutes} minutes.</p>"
        "</body></html>"
    )

    if settings.delivery_mode == "log":
        logger.info("Magic link email to=%s subject=%s link=%s", to_email, subject, magic_link)
        return

    if settings.delivery_mode != "email":
        logger.warning("Unsupported delivery mode=%s while sending magic links", settings.delivery_mode)
        return

    if not settings.resend_api_key:
        logger.warning("Missing RESEND_API_KEY while sending magic link to=%s", to_email)
        return

    payload = json.dumps(
        {
            "from": settings.from_email,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    ).encode("utf-8")

    request = Request(
        settings.resend_api_url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "sports-alerts-api/1.0",
        },
    )
    try:
        with urlopen(request, timeout=15.0) as response:
            if response.status >= 400:
                logger.warning("Resend rejected magic link delivery status=%s", response.status)
    except HTTPError as exc:
        logger.warning("Resend HTTP error delivering magic link status=%s", exc.code)
    except URLError as exc:
        logger.warning("Resend network error delivering magic link error=%s", exc.reason)
