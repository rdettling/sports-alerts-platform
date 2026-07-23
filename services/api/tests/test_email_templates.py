from datetime import datetime, timezone

from app.db.models import Game, SentAlert, Team
from app.services.email_templates import build_alert_email_content, build_alert_subject


def _mk_alert(alert_type: str) -> SentAlert:
    return SentAlert(
        user_id=1,
        game_id=1,
        alert_type=alert_type,
        delivery_channel="email",
        delivery_status="sent",
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


def test_world_cup_game_start_uses_country_logo_source_and_kickoff_copy():
    away = Team(external_team_id="203", league="WORLD_CUP", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", league="WORLD_CUP", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-1",
        league="WORLD_CUP",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=1,
        away_score=0,
        period=1,
        clock="12'",
    )
    alert = _mk_alert("game_start")

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject.startswith("Kickoff · MEX @ USA")
    assert "teamlogos/countries/500/mex.png" in html_body
    assert "teamlogos/countries/500/usa.png" in html_body
    assert "Kickoff is live now" in text_body


def test_mls_penalty_kicks_uses_club_logos_and_live_shootout_copy():
    away = Team(external_team_id="18966", league="MLS", name="LAFC", abbreviation="LAFC")
    home = Team(external_team_id="187", league="MLS", name="LA Galaxy", abbreviation="LA")
    game = Game(
        external_game_id="mls-penalties",
        league="MLS",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=1,
        away_score=1,
        period=5,
        clock="Pens",
    )
    alert = _mk_alert("penalty_kicks")
    alert.metadata_json = {"status": "in_progress", "period": 5, "clock": "Pens"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject == "Penalty kicks · LAFC 1–1 LA"
    assert "Penalty kicks are underway · LAFC 1–1 LA" in text_body
    assert "Penalties" in text_body
    assert "teamlogos/soccer/500/18966.png" in html_body
    assert "teamlogos/soccer/500/187.png" in html_body


def test_world_cup_score_changed_uses_inferred_goal_copy_from_metadata():
    away = Team(external_team_id="203", league="WORLD_CUP", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", league="WORLD_CUP", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-2",
        league="WORLD_CUP",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=1,
        away_score=1,
        period=1,
        clock="20'",
    )
    alert = _mk_alert("score_changed")
    alert.metadata_json = {
        "status": "in_progress",
        "period": 1,
        "clock": "18'",
        "previous_home_score": 0,
        "previous_away_score": 0,
        "new_home_score": 0,
        "new_away_score": 1,
        "scoring_side": "away",
        "is_inferred_goal": True,
    }

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Goal · MEX 1–0 USA"
    assert "Goal for MEX · MEX 1–0 USA" in text_body
    assert "18'" in text_body


def test_world_cup_score_changed_uses_generic_copy_for_ambiguous_update():
    away = Team(external_team_id="203", league="WORLD_CUP", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", league="WORLD_CUP", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-3",
        league="WORLD_CUP",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=3,
        away_score=2,
        period=2,
        clock="70'",
    )
    alert = _mk_alert("score_changed")
    alert.metadata_json = {
        "status": "in_progress",
        "period": 2,
        "clock": "68'",
        "previous_home_score": 1,
        "previous_away_score": 1,
        "new_home_score": 2,
        "new_away_score": 2,
        "scoring_side": None,
        "is_inferred_goal": False,
    }

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Score update · MEX 2–2 USA"
    assert "Score update · MEX 2–2 USA" in text_body
    assert "68'" in text_body


def test_world_cup_second_half_start_uses_resume_copy():
    away = Team(external_team_id="203", league="WORLD_CUP", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", league="WORLD_CUP", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-4",
        league="WORLD_CUP",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=0,
        away_score=0,
        period=2,
        clock="46'",
    )
    alert = _mk_alert("second_half_start")
    alert.metadata_json = {"status": "in_progress", "period": 2, "clock": "46'"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Second half · MEX 0–0 USA"
    assert "Second half is live now · MEX 0–0 USA" in text_body
    assert "46'" in text_body


def test_world_cup_extra_time_start_uses_literal_copy():
    away = Team(external_team_id="203", league="WORLD_CUP", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", league="WORLD_CUP", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-extra-time",
        league="WORLD_CUP",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=2,
        away_score=2,
        period=3,
        clock="91'",
    )
    alert = _mk_alert("extra_time_start")
    alert.metadata_json = {"status": "in_progress", "period": 3, "clock": "91'"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Extra time · MEX 2–2 USA"
    assert "Extra time is live now · MEX 2–2 USA" in text_body
    assert "91'" in text_body


def test_world_cup_penalty_kicks_uses_anticipatory_copy():
    away = Team(external_team_id="203", league="WORLD_CUP", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", league="WORLD_CUP", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-5",
        league="WORLD_CUP",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=1,
        away_score=1,
        period=3,
        clock="117'",
    )
    alert = _mk_alert("penalty_kicks")
    alert.metadata_json = {"status": "in_progress", "period": 3, "clock": "117'"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Penalty kicks likely soon · MEX 1–1 USA"
    assert "Match is still tied deep in extra time · MEX 1–1 USA" in text_body
    assert "117'" in text_body
