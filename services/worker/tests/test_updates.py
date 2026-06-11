from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import SportsUpdate, SportsUpdateSourceItem, SportsUpdateTeam, Team
from worker import updates


class DummyResponse:
    def __init__(self, *, text: str = "", json_body: dict | None = None):
        self.text = text
        self._json_body = json_body or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._json_body


RSS_BODY = """<?xml version="1.0" encoding="UTF-8" ?>
<rss>
  <channel>
    <item>
      <title>Celtics get healthy before finals push</title>
      <link>https://example.com/celtics-health?utm_source=test</link>
      <description>Boston receives a key injury boost.</description>
      <pubDate>Tue, 10 Jun 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

RSS_BODY_SHARED_CROSS_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss>
  <channel>
    <item>
      <title>Shared syndicated story</title>
      <link>https://example.com/shared-story?utm_source=test</link>
      <description>One URL appears in multiple league feeds.</description>
      <pubDate>Tue, 10 Jun 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

RSS_BODY_PROMO = """<?xml version="1.0" encoding="UTF-8" ?>
<rss>
  <channel>
    <item>
      <title>Use DraftKings promo code for $200 in bonus bets by targeting Knicks-Spurs NBA Finals Game 4, MLB on Wednesday</title>
      <link>https://www.cbssports.com/betting/news/use-draftkings-promo-code-for-200-bonus-bets-knicks-spurs-nba-finals-game-4-mlb-wednesday/</link>
      <description>DraftKings offers $200 in bonus bets instantly after your first $5 wager.</description>
      <pubDate>Tue, 10 Jun 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

RSS_BODY_FILLER = """<?xml version="1.0" encoding="UTF-8" ?>
<rss>
  <channel>
    <item>
      <title>Knicks vs. Spurs odds, prediction: 2026 NBA Finals picks, Game 4 best bets by model on 26-10 run</title>
      <link>https://www.cbssports.com/nba/news/knicks-vs-spurs-odds-prediction-2026-nba-finals-picks-game-4-best-bets-by-model-on-26-10-run/</link>
      <description>Odds, prediction and best bets for Game 4 of the NBA Finals.</description>
      <pubDate>Tue, 10 Jun 2026 12:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_ingest_updates_feed_creates_pending_items_once(monkeypatch, db_session):
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: DummyResponse(text=RSS_BODY))

    first = updates.ingest_updates_feed("NBA")
    second = updates.ingest_updates_feed("NBA")

    assert first["created"] == 1
    assert second["created"] == 0


def test_ingest_updates_feed_dedupes_source_items(monkeypatch, db_session):
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: DummyResponse(text=RSS_BODY))

    updates.ingest_updates_feed("NBA")

    source_items = db_session.scalars(select(SportsUpdateSourceItem)).all()
    classified_items = db_session.scalars(select(SportsUpdate)).all()
    assert len(source_items) == 1
    assert len(classified_items) == 1
    assert source_items[0].canonical_url == "https://example.com/celtics-health"
    assert classified_items[0].classifier_status == "pending"


def test_ingest_updates_feed_dedupes_shared_story_across_feeds(monkeypatch, db_session):
    def fake_get(url, *args, **kwargs):
        if "/nba/" in url or url.endswith("/nba/news"):
            return DummyResponse(text=RSS_BODY_SHARED_CROSS_FEED)
        if "/mlb/" in url or url.endswith("/mlb/news"):
            return DummyResponse(text=RSS_BODY_SHARED_CROSS_FEED)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(updates.httpx, "get", fake_get)

    first = updates.ingest_updates_feed("NBA")
    second = updates.ingest_updates_feed("MLB")

    source_items = db_session.scalars(select(SportsUpdateSourceItem)).all()
    classified_items = db_session.scalars(select(SportsUpdate)).all()
    assert first["created"] == 1
    assert second["created"] == 0
    assert len(source_items) == 1
    assert len(classified_items) == 1


def test_ingest_updates_feed_suppresses_betting_promotions(monkeypatch, db_session):
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: DummyResponse(text=RSS_BODY_PROMO))

    result = updates.ingest_updates_feed("NBA")

    source_items = db_session.scalars(select(SportsUpdateSourceItem)).all()
    classified_items = db_session.scalars(select(SportsUpdate)).all()
    assert result["fetched"] == 0
    assert result["created"] == 0
    assert source_items == []
    assert classified_items == []


def test_ingest_updates_feed_suppresses_odds_and_prediction_filler(monkeypatch, db_session):
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: DummyResponse(text=RSS_BODY_FILLER))

    result = updates.ingest_updates_feed("NBA")

    source_items = db_session.scalars(select(SportsUpdateSourceItem)).all()
    classified_items = db_session.scalars(select(SportsUpdate)).all()
    assert result["fetched"] == 0
    assert result["created"] == 0
    assert source_items == []
    assert classified_items == []


def test_classify_pending_updates_leaves_items_pending_without_openai_key(monkeypatch, db_session):
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: DummyResponse(text=RSS_BODY))
    monkeypatch.setattr(updates.settings, "openai_api_key", "")

    updates.ingest_updates_feed("NBA")
    result = updates.classify_pending_updates()

    pending = db_session.scalars(select(SportsUpdate)).all()
    assert result["processed"] == 0
    assert len(pending) == 1
    assert pending[0].classifier_status == "pending"


def test_classify_pending_updates_stores_structured_output(monkeypatch, db_session):
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: DummyResponse(text=RSS_BODY))
    monkeypatch.setattr(updates.settings, "openai_api_key", "test-openai-key")

    def fake_post(*args, **kwargs):
        return DummyResponse(
            json_body={
                "output_text": """{
                    "scope": "team",
                    "league": "NBA",
                    "team_refs": [2],
                    "importance": "high",
                    "tags": ["injury", "playoffs"],
                    "reason": "Direct Boston team news.",
                    "confidence": "high"
                }"""
            }
        )

    monkeypatch.setattr(updates.httpx, "post", fake_post)

    updates.ingest_updates_feed("NBA")
    result = updates.classify_pending_updates()

    update = db_session.scalar(select(SportsUpdate))
    team_links = db_session.scalars(select(SportsUpdateTeam)).all()
    assert result["classified"] == 1
    assert update is not None
    assert update.classifier_status == "classified"
    assert update.scope == "team"
    assert update.importance == "high"
    assert update.tags_json == ["injury", "playoffs"]
    assert len(team_links) == 1
    assert team_links[0].team_id == 2


def test_classify_pending_updates_parses_responses_api_output_shape(monkeypatch, db_session):
    monkeypatch.setattr(updates.httpx, "get", lambda *args, **kwargs: DummyResponse(text=RSS_BODY))
    monkeypatch.setattr(updates.settings, "openai_api_key", "test-openai-key")

    def fake_post(*args, **kwargs):
        return DummyResponse(
            json_body={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": """{
                                    "scope": "league",
                                    "league": "NBA",
                                    "team_refs": [],
                                    "importance": "medium",
                                    "tags": ["league"],
                                    "reason": "League-wide story.",
                                    "confidence": "medium"
                                }""",
                            }
                        ],
                    }
                ]
            }
        )

    monkeypatch.setattr(updates.httpx, "post", fake_post)

    updates.ingest_updates_feed("NBA")
    result = updates.classify_pending_updates()

    update = db_session.scalar(select(SportsUpdate))
    assert result["classified"] == 1
    assert update is not None
    assert update.classifier_status == "classified"
    assert update.scope == "league"
    assert update.league == "NBA"
