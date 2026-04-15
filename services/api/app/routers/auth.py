import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import EmailLoginToken, User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.auth import (
    AuthTokenResponse,
    MagicLinkStartRequest,
    MagicLinkStartResponse,
    MagicLinkVerifyRequest,
    UserOut,
)
from app.services.magic_link_delivery import send_magic_link_email
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
NEUTRAL_START_MESSAGE = "If that email can receive login links, one has been sent."


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _make_magic_link(token: str) -> str:
    base_url = settings.web_base_url.rstrip("/")
    return f"{base_url}/auth?token={quote_plus(token)}"


@router.post("/magic-link/start", response_model=MagicLinkStartResponse)
def start_magic_link(
    payload: MagicLinkStartRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MagicLinkStartResponse:
    now = datetime.now(timezone.utc)
    email = _normalize_email(str(payload.email))
    one_hour_ago = now - timedelta(hours=1)
    cooldown_cutoff = now - timedelta(seconds=settings.magic_link_cooldown_seconds)

    requests_last_hour = db.scalar(
        select(func.count(EmailLoginToken.id)).where(
            EmailLoginToken.email == email,
            EmailLoginToken.created_at >= one_hour_ago,
        )
    ) or 0
    recent_request_exists = db.scalar(
        select(EmailLoginToken.id).where(
            EmailLoginToken.email == email,
            EmailLoginToken.created_at >= cooldown_cutoff,
        )
    )

    if recent_request_exists or requests_last_hour >= settings.magic_link_max_requests_per_hour:
        return MagicLinkStartResponse(message=NEUTRAL_START_MESSAGE)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    login_token = EmailLoginToken(
        email=email,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=settings.magic_link_ttl_minutes),
        requested_ip=request.client.host if request.client else None,
        requested_user_agent=request.headers.get("user-agent"),
    )
    db.add(login_token)
    db.commit()

    magic_link = _make_magic_link(raw_token)
    send_magic_link_email(email, magic_link)
    return MagicLinkStartResponse(message=NEUTRAL_START_MESSAGE)


@router.post("/magic-link/verify", response_model=AuthTokenResponse)
def verify_magic_link(payload: MagicLinkVerifyRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    now = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()

    token_row = db.scalar(
        select(EmailLoginToken).where(
            EmailLoginToken.token_hash == token_hash,
            EmailLoginToken.consumed_at.is_(None),
            EmailLoginToken.expires_at > now,
        )
    )
    if not token_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    consume_result = db.execute(
        update(EmailLoginToken)
        .where(
            EmailLoginToken.id == token_row.id,
            EmailLoginToken.consumed_at.is_(None),
            EmailLoginToken.expires_at > now,
        )
        .values(consumed_at=now)
        .execution_options(synchronize_session=False)
    )
    if consume_result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.scalar(select(User).where(User.email == token_row.email))
    if not user:
        user = User(email=token_row.email)
        db.add(user)
        db.flush()

    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id))
    return AuthTokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
