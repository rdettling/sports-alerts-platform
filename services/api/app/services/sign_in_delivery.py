from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.services.delivery_settings import delivery_settings
from app.services.resend import send_resend_email
from app.services.sign_in_email import build_sign_in_email

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

    result = send_resend_email(
        db,
        service="api",
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    if result.sent:
        return

    metadata = result.metadata or {}
    error = metadata.get("error", "unknown_error")
    if error == "missing_resend_api_key":
        logger.warning("Missing RESEND_API_KEY while sending sign-in email to=%s", to_email)
    elif metadata.get("status_code") is not None:
        logger.warning("Resend rejected sign-in email status=%s", metadata["status_code"])
    else:
        logger.warning("Resend error delivering sign-in email error=%s", metadata.get("detail", error))
