from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import SportsUpdate, SportsUpdateSourceItem, SportsUpdateTeam, Team, User, UserLeagueFollow, UserTeamFollow
from app.db.session import SessionLocal


def _auth_headers(email: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _team_by_abbr(league: str, abbr: str) -> Team:
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.league == league, Team.abbreviation == abbr))
        assert team is not None
        db.expunge(team)
        return team
    finally:
        db.close()


def _create_update(
    *,
    league: str,
    title: str,
    summary: str,
    published_at: datetime,
    scope: str,
    importance: str,
    team_ids: list[int] | None = None,
) -> None:
    db = SessionLocal()
    try:
        source = SportsUpdateSourceItem(
            source_type="rss",
            source_name="CBS Sports",
            feed_key=f"test-{league.lower()}",
            league=league,
            title=title,
            summary=summary,
            article_url=f"https://example.com/{title.replace(' ', '-').lower()}",
            canonical_url=f"https://example.com/{title.replace(' ', '-').lower()}",
            published_at=published_at,
            dedupe_key=f"{league}:{title}",
            raw_payload_json={"title": title},
        )
        db.add(source)
        db.flush()
        update = SportsUpdate(
            source_item_id=source.id,
            league=league,
            scope=scope,
            importance=importance,
            confidence="high",
            tags_json=["test"],
            reason="test reason",
            classifier_status="classified",
        )
        db.add(update)
        db.flush()
        for team_id in team_ids or []:
            db.add(SportsUpdateTeam(sports_update_id=update.id, team_id=team_id))
        db.commit()
    finally:
        db.close()


def test_updates_feed_ranks_team_matches_above_league_matches(client):
    bos = _team_by_abbr("NBA", "BOS")
    _create_update(
        league="NBA",
        title="Boston gets major injury boost",
        summary="Team-specific update",
        published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        scope="team",
        importance="high",
        team_ids=[bos.id],
    )
    _create_update(
        league="NBA",
        title="NBA lottery rules updated",
        summary="League-wide update",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        scope="league",
        importance="critical",
    )

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "updates-team@example.com"))
        if not user:
            user = User(email="updates-team@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
        db.add(UserTeamFollow(user_id=user.id, team_id=bos.id))
        db.add(UserLeagueFollow(user_id=user.id, league="NBA"))
        db.commit()
    finally:
        db.close()

    response = client.get("/updates", headers=_auth_headers("updates-team@example.com"))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 2
    assert items[0]["title"] == "Boston gets major injury boost"
    assert items[0]["matched_scope"] == "team"


def test_updates_feed_shows_league_scoped_items_for_league_followers(client):
    _create_update(
        league="MLB",
        title="MLB changes replay rules",
        summary="League update",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        scope="league",
        importance="high",
    )

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "updates-league@example.com"))
        if not user:
            user = User(email="updates-league@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
        db.add(UserLeagueFollow(user_id=user.id, league="MLB"))
        db.commit()
    finally:
        db.close()

    response = client.get("/updates", headers=_auth_headers("updates-league@example.com"))
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert items[0]["league"] == "MLB"
    assert items[0]["matched_scope"] == "league"


def test_updates_feed_can_surface_high_importance_team_story_to_league_follower(client):
    bos = _team_by_abbr("NBA", "BOS")
    _create_update(
        league="NBA",
        title="Boston loses star guard for postseason",
        summary="Team update with league-wide significance",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        scope="team",
        importance="critical",
        team_ids=[bos.id],
    )

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "updates-league-team@example.com"))
        if not user:
            user = User(email="updates-league-team@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
        db.add(UserLeagueFollow(user_id=user.id, league="NBA"))
        db.commit()
    finally:
        db.close()

    response = client.get("/updates", headers=_auth_headers("updates-league-team@example.com"))
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert items[0]["title"] == "Boston loses star guard for postseason"
    assert items[0]["matched_scope"] == "league"


def test_updates_feed_hides_non_relevant_items(client):
    _create_update(
        league="MLB",
        title="MLB changes replay rules",
        summary="League update",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        scope="league",
        importance="high",
    )

    response = client.get("/updates", headers=_auth_headers("updates-none@example.com"))
    assert response.status_code == 200
    assert response.json()["items"] == []
