from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import SportsUpdate, SportsUpdateSourceItem, SportsUpdateTeam, Team
from worker.config import settings
from worker.db import SessionLocal

logger = logging.getLogger(__name__)

CLASSIFIER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scope": {"type": "string", "enum": ["team", "league", "ignore"]},
        "league": {"type": ["string", "null"], "enum": ["NBA", "MLB", None]},
        "team_refs": {"type": "array", "items": {"type": "integer"}, "maxItems": 6},
        "importance": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "reason": {"type": "string", "maxLength": 400},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["scope", "league", "team_refs", "importance", "tags", "reason", "confidence"],
}


@dataclass(frozen=True)
class FeedConfig:
    league: str
    feed_key: str
    source_name: str
    url: str


FEEDS: dict[str, FeedConfig] = {
    "NBA": FeedConfig(league="NBA", feed_key="cbs_nba", source_name="CBS Sports", url=settings.updates_rss_nba_url),
    "MLB": FeedConfig(league="MLB", feed_key="cbs_mlb", source_name="CBS Sports", url=settings.updates_rss_mlb_url),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, "", ""))


def _normalize_title(text: str) -> str:
    return " ".join(text.lower().split())


def _dedupe_key(*, canonical_url: str, league: str, source_name: str, title: str, published_at: datetime | None) -> str:
    if canonical_url:
        return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
    bucket = published_at.strftime("%Y%m%d%H") if published_at else "unknown"
    fallback = f"{league}|{source_name}|{bucket}|{_normalize_title(title)}"
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_text(node: ElementTree.Element, tag: str) -> str | None:
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _fetch_feed_items(feed: FeedConfig) -> list[dict[str, Any]]:
    response = httpx.get(feed.url, timeout=15.0, follow_redirects=True)
    response.raise_for_status()
    root = ElementTree.fromstring(response.text)
    items: list[dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        title = _extract_text(item, "title")
        link = _extract_text(item, "link")
        if not title or not link:
            continue
        summary = _extract_text(item, "description")
        published_at = _parse_datetime(_extract_text(item, "pubDate"))
        canonical_url = _canonicalize_url(link)
        dedupe_key = _dedupe_key(
            canonical_url=canonical_url,
            league=feed.league,
            source_name=feed.source_name,
            title=title,
            published_at=published_at,
        )
        items.append(
            {
                "title": title,
                "summary": summary,
                "article_url": link,
                "canonical_url": canonical_url,
                "published_at": published_at,
                "dedupe_key": dedupe_key,
                "raw_payload_json": {
                    "title": title,
                    "summary": summary,
                    "article_url": link,
                    "canonical_url": canonical_url,
                    "published_at": published_at.isoformat() if published_at else None,
                    "dedupe_key": dedupe_key,
                },
            }
        )
    return items


def ingest_updates_feed(league: str) -> dict[str, int]:
    feed = FEEDS[league]
    items = _fetch_feed_items(feed)
    db = SessionLocal()
    created_count = 0
    try:
        existing_keys = {
            dedupe_key
            for dedupe_key, in db.execute(
                select(SportsUpdateSourceItem.dedupe_key).where(
                    SportsUpdateSourceItem.dedupe_key.in_([item["dedupe_key"] for item in items]),
                )
            ).all()
        }
        for item in items:
            if item["dedupe_key"] in existing_keys:
                continue
            source_item = SportsUpdateSourceItem(
                source_type="rss",
                source_name=feed.source_name,
                feed_key=feed.feed_key,
                league=feed.league,
                title=item["title"],
                summary=item["summary"],
                article_url=item["article_url"],
                canonical_url=item["canonical_url"],
                published_at=item["published_at"],
                dedupe_key=item["dedupe_key"],
                raw_payload_json=item["raw_payload_json"],
            )
            db.add(source_item)
            db.flush()
            db.add(
                SportsUpdate(
                    source_item_id=source_item.id,
                    league=feed.league,
                    classifier_status="pending",
                )
            )
            existing_keys.add(item["dedupe_key"])
            created_count += 1
        db.commit()
    finally:
        db.close()
    logger.info("Updates ingest league=%s fetched=%s created=%s", league, len(items), created_count)
    return {"fetched": len(items), "created": created_count}


def _classification_prompt(source: SportsUpdateSourceItem, teams: list[Team]) -> list[dict[str, str]]:
    team_lines = "\n".join(f"- id={team.id}; name={team.name}; abbr={team.abbreviation}" for team in teams)
    developer = (
        "You classify sports news updates for a personalized NBA/MLB dashboard.\n"
        "Return only structured JSON matching the schema.\n"
        "Choose scope='league' for league-wide developments, rule changes, draft changes, or stories not centered on one team.\n"
        "Choose scope='team' only when the update is specifically about one or more teams.\n"
        "Choose scope='ignore' for weak, low-signal, generic, or irrelevant items.\n"
        "Only use team_refs from the provided team list."
    )
    user = (
        f"League feed: {source.league}\n"
        f"Source: {source.source_name}\n"
        f"Published: {source.published_at.isoformat() if source.published_at else 'unknown'}\n"
        f"Title: {source.title}\n"
        f"Summary: {source.summary or ''}\n\n"
        f"Available teams for {source.league}:\n{team_lines}"
    )
    return [
        {"role": "developer", "content": developer},
        {"role": "user", "content": user},
    ]


def _classify_with_openai(source: SportsUpdateSourceItem, teams: list[Team]) -> dict[str, Any]:
    response = httpx.post(
        f"{settings.openai_api_base_url.rstrip('/')}/responses",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openai_updates_model,
            "input": _classification_prompt(source, teams),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "sports_update_classification",
                    "strict": True,
                    "schema": CLASSIFIER_SCHEMA,
                }
            },
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    output_text = payload.get("output_text")
    if (not isinstance(output_text, str) or not output_text.strip()) and isinstance(payload.get("output"), list):
        for item in payload["output"]:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "output_text" and isinstance(content.get("text"), str) and content["text"].strip():
                    output_text = content["text"]
                    break
            if isinstance(output_text, str) and output_text.strip():
                break
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("OpenAI classification returned empty output_text")
    return json.loads(output_text)


def _validate_classification(raw: dict[str, Any], league: str, valid_team_ids: set[int]) -> dict[str, Any]:
    scope = raw.get("scope")
    if scope not in {"team", "league", "ignore"}:
        raise ValueError("Invalid scope")
    resolved_league = raw.get("league")
    if scope == "ignore":
        resolved_league = league if resolved_league not in {"NBA", "MLB"} else resolved_league
    elif resolved_league not in {"NBA", "MLB"}:
        raise ValueError("Invalid league")
    importance = raw.get("importance")
    if importance not in {"low", "medium", "high", "critical"}:
        raise ValueError("Invalid importance")
    confidence = raw.get("confidence")
    if confidence not in {"low", "medium", "high"}:
        raise ValueError("Invalid confidence")
    team_refs = [team_id for team_id in raw.get("team_refs", []) if team_id in valid_team_ids]
    tags = [str(tag).strip() for tag in raw.get("tags", []) if str(tag).strip()]
    reason = str(raw.get("reason", "")).strip()
    return {
        "scope": scope,
        "league": resolved_league,
        "importance": importance,
        "confidence": confidence,
        "team_refs": team_refs,
        "tags": tags[:6],
        "reason": reason[:400],
    }


def classify_pending_updates(limit: int | None = None) -> dict[str, int]:
    batch_size = limit or settings.updates_classify_batch_size
    db = SessionLocal()
    try:
        pending_count = db.scalar(
            select(func.count(SportsUpdate.id)).where(SportsUpdate.classifier_status.in_(("pending", "failed")))
        ) or 0
        if pending_count == 0:
            return {"processed": 0, "pending": 0, "classified": 0}
        if not settings.openai_api_key.strip():
            return {"processed": 0, "pending": pending_count, "classified": 0}

        rows = db.execute(
            select(SportsUpdate, SportsUpdateSourceItem)
            .join(SportsUpdateSourceItem, SportsUpdate.source_item_id == SportsUpdateSourceItem.id)
            .where(SportsUpdate.classifier_status.in_(("pending", "failed")))
            .order_by(SportsUpdate.created_at.asc(), SportsUpdate.id.asc())
            .limit(batch_size)
        ).all()
        classified_count = 0
        for update, source in rows:
            teams = db.scalars(select(Team).where(Team.league == source.league).order_by(Team.name.asc())).all()
            try:
                parsed = _validate_classification(
                    _classify_with_openai(source, teams),
                    source.league,
                    {team.id for team in teams},
                )
            except Exception as exc:
                update.attempt_count += 1
                update.last_attempted_at = _now()
                update.classifier_status = "failed"
                update.last_error = str(exc)[:2000]
                db.commit()
                logger.warning("Updates classify failed update_id=%s error=%s", update.id, exc)
                continue

            update.attempt_count += 1
            update.last_attempted_at = _now()
            update.classifier_status = "classified"
            update.classifier_version = settings.updates_classifier_version
            update.scope = parsed["scope"]
            update.league = parsed["league"]
            update.importance = parsed["importance"]
            update.confidence = parsed["confidence"]
            update.tags_json = parsed["tags"]
            update.reason = parsed["reason"]
            update.classified_at = _now()
            update.last_error = None
            db.execute(delete(SportsUpdateTeam).where(SportsUpdateTeam.sports_update_id == update.id))
            for team_id in parsed["team_refs"]:
                db.add(SportsUpdateTeam(sports_update_id=update.id, team_id=team_id))
            db.commit()
            classified_count += 1
        return {"processed": len(rows), "pending": max(0, pending_count - classified_count), "classified": classified_count}
    finally:
        db.close()
