from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SportsUpdate, SportsUpdateSourceItem, SportsUpdateTeam, Team, User, UserLeagueFollow, UserTeamFollow
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.update import SportsUpdateOut, SportsUpdatesFeedOut

router = APIRouter(prefix="/updates", tags=["updates"])

IMPORTANCE_SCORES = {"critical": 400, "high": 300, "medium": 200, "low": 100}
SOURCE_TRUST_SCORES = {"CBS Sports": 100}
LEAGUE_VISIBLE_TEAM_IMPORTANCE = {"high", "critical"}


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _score_update(
    *,
    importance: str,
    published_at: datetime | None,
    source_name: str,
    team_match: bool,
    league_match: bool,
) -> float:
    score = float(IMPORTANCE_SCORES.get(importance, 0))
    published_at = _coerce_utc(published_at)
    if team_match:
        score += 1000
    elif league_match:
        score += 500
    score += float(SOURCE_TRUST_SCORES.get(source_name, 50))
    if published_at is not None:
        hours_old = max(0.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)
        score -= min(200.0, hours_old * 4.0)
    return score


@router.get("", response_model=SportsUpdatesFeedOut)
def list_updates(
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SportsUpdatesFeedOut:
    followed_team_ids = {
        team_id
        for team_id, in db.execute(
            select(UserTeamFollow.team_id).where(UserTeamFollow.user_id == current_user.id)
        ).all()
    }
    followed_leagues = {
        league
        for league, in db.execute(
            select(UserLeagueFollow.league).where(UserLeagueFollow.user_id == current_user.id)
        ).all()
    }

    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    rows = db.execute(
        select(SportsUpdate, SportsUpdateSourceItem)
        .join(SportsUpdateSourceItem, SportsUpdate.source_item_id == SportsUpdateSourceItem.id)
        .where(SportsUpdate.classifier_status == "classified")
        .where(SportsUpdate.scope.in_(("team", "league")))
        .where(SportsUpdateSourceItem.published_at.is_(None) | (SportsUpdateSourceItem.published_at >= recent_cutoff))
        .order_by(SportsUpdateSourceItem.published_at.desc().nullslast(), SportsUpdate.id.desc())
        .limit(300)
    ).all()

    update_ids = [update.id for update, _source in rows]
    team_rows = db.execute(
        select(SportsUpdateTeam.sports_update_id, Team.abbreviation, Team.id)
        .join(Team, Team.id == SportsUpdateTeam.team_id)
        .where(SportsUpdateTeam.sports_update_id.in_(update_ids))
    ).all() if update_ids else []

    teams_by_update: dict[int, list[tuple[int, str]]] = {}
    for update_id, abbr, team_id in team_rows:
        teams_by_update.setdefault(update_id, []).append((team_id, abbr))

    ranked: list[tuple[float, SportsUpdateOut]] = []
    for update, source in rows:
        attached_teams = teams_by_update.get(update.id, [])
        attached_team_ids = {team_id for team_id, _abbr in attached_teams}
        team_match = bool(followed_team_ids & attached_team_ids)
        league_match = bool(update.league and update.league in followed_leagues)

        visible = False
        matched_scope = ""
        if team_match:
            visible = True
            matched_scope = "team"
        elif update.scope == "league" and league_match:
            visible = True
            matched_scope = "league"
        elif update.scope == "team" and league_match and update.importance in LEAGUE_VISIBLE_TEAM_IMPORTANCE:
            visible = True
            matched_scope = "league"

        if not visible or not update.league or not update.scope or not update.importance:
            continue

        score = _score_update(
            importance=update.importance,
            published_at=source.published_at,
            source_name=source.source_name,
            team_match=team_match,
            league_match=league_match,
        )
        ranked.append(
            (
                score,
                SportsUpdateOut(
                    id=update.id,
                    title=source.title,
                    summary=source.summary,
                    article_url=source.article_url,
                    source_name=source.source_name,
                    published_at=_coerce_utc(source.published_at),
                    league=update.league,
                    scope=update.scope,
                    importance=update.importance,
                    confidence=update.confidence,
                    tags=update.tags_json or [],
                    reason=update.reason,
                    team_abbreviations=[abbr for _team_id, abbr in sorted(attached_teams, key=lambda item: item[1])],
                    matched_scope=matched_scope,
                ),
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1].published_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return SportsUpdatesFeedOut(items=[item for _score, item in ranked[:limit]])
