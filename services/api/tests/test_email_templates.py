from datetime import datetime, timezone

from app.db.models import Game, SentAlert, Team
from app.services.email_templates import build_alert_email_content, build_alert_subject


def _mk_alert(alert_type: str) -> SentAlert:
    return SentAlert(
        user_id=1,
        game_id=1,
        alert_type=alert_type,
        delivery_channel="email",
        delivery_status="pending",
        dedupe_key=f"1:1:{alert_type}",
    )


def test_mlb_inning_start_uses_mlb_logos_and_non_nba_details():
    away = Team(external_team_id="MIA", league="MLB", name="Miami Marlins", abbreviation="MIA")
    home = Team(external_team_id="TOR", league="MLB", name="Toronto Blue Jays", abbreviation="TOR")
    game = Game(
        external_game_id="mlb-1",
        league="MLB",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=2,
        away_score=1,
        period=7,
        clock="Mid 7th",
    )
    alert = _mk_alert("inning_start")

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject.startswith("Inning start · MIA @ TOR")
    assert "teamlogos/mlb/500/mia.png" in html_body
    assert "teamlogos/mlb/500/tor.png" in html_body
    assert "OT" not in text_body
    assert "Mid 7th left" not in text_body
    assert "Mid 7th" in text_body


def test_nba_game_start_keeps_tipoff_and_nba_logo_source():
    away = Team(external_team_id="2", league="NBA", name="Boston Celtics", abbreviation="BOS")
    home = Team(external_team_id="13", league="NBA", name="Los Angeles Lakers", abbreviation="LAL")
    game = Game(
        external_game_id="nba-1",
        league="NBA",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=101,
        away_score=99,
    )
    alert = _mk_alert("game_start")

    subject = build_alert_subject(alert, game, home, away)
    _, html_body = build_alert_email_content(alert, game, home, away)

    assert subject.startswith("Tip-off · BOS @ LAL")
    assert "teamlogos/nba/500/bos.png" in html_body
    assert "teamlogos/nba/500/lal.png" in html_body


def test_unknown_league_falls_back_to_generic_and_no_logo_urls():
    away = Team(external_team_id="X1", league="NHL", name="Away Team", abbreviation="AWY")
    home = Team(external_team_id="X2", league="NHL", name="Home Team", abbreviation="HOM")
    game = Game(
        external_game_id="other-1",
        league="NHL",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=3,
        away_score=2,
    )
    alert = _mk_alert("game_start")

    subject = build_alert_subject(alert, game, home, away)
    _, html_body = build_alert_email_content(alert, game, home, away)

    assert subject.startswith("Game start · AWY @ HOM")
    assert "teamlogos/nba/500/" not in html_body
    assert "teamlogos/mlb/500/" not in html_body
