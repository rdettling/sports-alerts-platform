from datetime import datetime, timezone

from app.db.models import Alert, Game, Team
from app.services.alert_content import (
    build_alert_email_content,
    build_alert_push_content,
    build_alert_subject,
)


def _mk_alert(alert_type: str) -> Alert:
    return Alert(
        user_id=1,
        game_id=1,
        alert_type=alert_type,
        event_key=f"1:1:{alert_type}",
    )


def test_mlb_inning_start_uses_mlb_logos_and_non_nba_details():
    away = Team(external_team_id="MIA", name="Miami Marlins", abbreviation="MIA")
    home = Team(external_team_id="TOR", name="Toronto Blue Jays", abbreviation="TOR")
    game = Game(
        external_game_id="mlb-1",
        competition="MLB",
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


def test_mlb_extra_innings_start_uses_ordinal_inning_copy():
    away = Team(external_team_id="MIA", name="Miami Marlins", abbreviation="MIA")
    home = Team(external_team_id="TOR", name="Toronto Blue Jays", abbreviation="TOR")
    game = Game(
        external_game_id="mlb-extra-innings",
        competition="MLB",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=3,
        away_score=3,
        period=11,
        clock="Top 11th",
    )
    alert = _mk_alert("extra_innings_start")
    alert.event_data = {"status": "in_progress", "period": 10, "clock": "Top 10th"}
    assert build_alert_subject(alert, game, home, away) == "10th inning · MIA 3–3 TOR"

    alert.event_data = {"status": "in_progress", "period": 11, "clock": "Top 11th"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject == "11th inning · MIA 3–3 TOR"
    assert "Extra innings start" in text_body
    assert "11th inning is underway · MIA 3–3 TOR" in text_body
    assert "In Progress • Inning 11 • Top 11th" in text_body
    assert "11th inning is underway · MIA 3–3 TOR" in html_body


def test_nba_game_start_keeps_tipoff_and_nba_logo_source():
    away = Team(external_team_id="2", name="Boston Celtics", abbreviation="BOS")
    home = Team(external_team_id="13", name="Los Angeles Lakers", abbreviation="LAL")
    game = Game(
        external_game_id="nba-1",
        competition="NBA",
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


def test_delayed_delivery_uses_event_snapshot_after_game_changes():
    away = Team(external_team_id="2", name="Boston Celtics", abbreviation="BOS")
    home = Team(external_team_id="13", name="Los Angeles Lakers", abbreviation="LAL")
    game = Game(
        external_game_id="nba-delayed-final",
        competition="NBA",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=120,
        away_score=118,
        period=5,
        clock="03:00",
    )
    alert = _mk_alert("final_result")
    alert.event_data = {
        "status": "final",
        "period": 4,
        "clock": "0:00",
        "home_score": 109,
        "away_score": 105,
    }

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Final · BOS 105–109 LAL"
    assert "BOS (105) @ LAL (109)" in text_body
    assert "Final • Q4 • 0:00 left" in text_body


def test_wnba_game_start_uses_basketball_copy_and_wnba_logos():
    away = Team(external_team_id="17", name="Las Vegas Aces", abbreviation="LV")
    home = Team(external_team_id="9", name="New York Liberty", abbreviation="NY")
    game = Game(
        external_game_id="wnba-1",
        competition="WNBA",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=81,
        away_score=79,
    )

    subject = build_alert_subject(_mk_alert("game_start"), game, home, away)
    _, html_body = build_alert_email_content(_mk_alert("game_start"), game, home, away)

    assert subject.startswith("Tip-off · LV @ NY")
    assert "teamlogos/wnba/500/lv.png" in html_body
    assert "teamlogos/wnba/500/ny.png" in html_body


def test_nfl_alerts_use_football_copy_periods_and_logos():
    away = Team(external_team_id="12", name="Kansas City Chiefs", abbreviation="KC")
    home = Team(external_team_id="2", name="Buffalo Bills", abbreviation="BUF")
    game = Game(
        external_game_id="nfl-1",
        competition="NFL",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=20,
        away_score=17,
        period=4,
        clock="04:30",
    )

    start_subject = build_alert_subject(_mk_alert("game_start"), game, home, away)
    close_text, close_html = build_alert_email_content(_mk_alert("close_game_late"), game, home, away)

    assert start_subject == "Kickoff · KC @ BUF"
    assert "KC 17–20 BUF • Q4 • 04:30 left" in close_text
    assert "teamlogos/nfl/500/kc.png" in close_html
    assert "teamlogos/nfl/500/buf.png" in close_html

    game.home_score = 20
    game.away_score = 20
    game.period = 5
    game.clock = "10:00"
    overtime = _mk_alert("overtime_start")
    overtime.event_data = {"status": "in_progress", "period": 5, "clock": "10:00"}
    assert build_alert_subject(overtime, game, home, away) == "OT1 · KC 20–20 BUF"


def test_football_score_and_lead_alerts_use_event_time_scores():
    away = Team(external_team_id="12", name="Kansas City Chiefs", abbreviation="KC")
    home = Team(external_team_id="2", name="Buffalo Bills", abbreviation="BUF")
    game = Game(
        external_game_id="nfl-score-events",
        competition="NFL",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=28,
        away_score=24,
        period=4,
        clock="01:00",
    )
    score_update = _mk_alert("score_changed")
    score_update.event_data = {
        "status": "in_progress",
        "period": 3,
        "clock": "06:42",
        "previous_home_score": 7,
        "previous_away_score": 14,
        "new_home_score": 10,
        "new_away_score": 14,
        "scoring_side": "home",
        "is_inferred_goal": False,
        "previous_leader": "away",
        "new_leader": "away",
    }

    subject = build_alert_subject(score_update, game, home, away)
    text_body, _ = build_alert_email_content(score_update, game, home, away)

    assert subject == "Score update · KC 14–10 BUF"
    assert "Score update · KC 14–10 BUF" in text_body
    assert "In Progress • Q3 • 06:42 left" in text_body

    lead_change = _mk_alert("lead_change")
    lead_change.event_data = {
        **score_update.event_data,
        "period": 4,
        "clock": "08:42",
        "previous_home_score": 17,
        "previous_away_score": 21,
        "new_home_score": 24,
        "new_away_score": 21,
        "previous_leader": "away",
        "new_leader": "home",
        "covers_close_game_late": True,
    }
    subject = build_alert_subject(lead_change, game, home, away)
    text_body, _ = build_alert_email_content(lead_change, game, home, away)

    assert subject == "BUF takes the lead · KC 21–24 BUF"
    assert "BUF takes the lead · KC 21–24 BUF" in text_body
    assert "In Progress • Q4 • 08:42 left" in text_body
    assert build_alert_push_content(lead_change, game, home, away) == (
        "BUF takes the lead · KC 21–24 BUF",
        "BUF takes the lead · KC 21–24 BUF • Q4 • 08:42 left",
    )

    close_game = _mk_alert("close_game_late")
    close_game.event_data = {
        **score_update.event_data,
        "period": 4,
        "clock": "03:00",
        "previous_home_score": 20,
        "previous_away_score": 10,
        "new_home_score": 20,
        "new_away_score": 13,
    }
    close_text, _ = build_alert_email_content(close_game, game, home, away)
    assert build_alert_subject(close_game, game, home, away) == "Close game · KC 13–20 BUF"
    assert "KC 13–20 BUF • Q4 • 03:00 left" in close_text

    lead_change.event_data = {
        **lead_change.event_data,
        "new_home_score": 21,
        "new_away_score": 21,
        "new_leader": "tied",
    }
    assert build_alert_subject(lead_change, game, home, away) == "Game tied · KC 21–21 BUF"


def test_fbs_alerts_use_football_copy_and_ncaa_team_logos():
    away = Team(external_team_id="2", name="Auburn Tigers", abbreviation="AUB")
    home = Team(external_team_id="333", name="Alabama Crimson Tide", abbreviation="ALA")
    game = Game(
        external_game_id="fbs-1",
        competition="FBS",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=24,
        away_score=21,
        period=4,
        clock="02:00",
    )

    subject = build_alert_subject(_mk_alert("game_start"), game, home, away)
    text_body, html_body = build_alert_email_content(
        _mk_alert("close_game_late"), game, home, away
    )

    assert subject == "Kickoff · AUB @ ALA"
    assert "AUB 21–24 ALA • Q4 • 02:00 left" in text_body
    assert "teamlogos/ncaa/500/2.png" in html_body
    assert "teamlogos/ncaa/500/333.png" in html_body


def test_nba_overtime_start_uses_period_aware_copy():
    away = Team(external_team_id="13", name="Los Angeles Lakers", abbreviation="LAL")
    home = Team(external_team_id="2", name="Boston Celtics", abbreviation="BOS")
    game = Game(
        external_game_id="nba-overtime",
        competition="NBA",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=112,
        away_score=112,
        period=6,
        clock="05:00",
    )
    alert = _mk_alert("overtime_start")
    alert.event_data = {"status": "in_progress", "period": 6, "clock": "05:00"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject == "OT2 · LAL 112–112 BOS"
    assert "Overtime start" in text_body
    assert "OT2 is live now · LAL 112–112 BOS" in text_body
    assert "In Progress • OT2 • 05:00 left" in text_body
    assert "OT2 is live now · LAL 112–112 BOS" in html_body


def test_unknown_competition_falls_back_to_generic_and_no_logo_urls():
    away = Team(external_team_id="X1", name="Away Team", abbreviation="AWY")
    home = Team(external_team_id="X2", name="Home Team", abbreviation="HOM")
    game = Game(
        external_game_id="other-1",
        competition="NHL",
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
    away = Team(external_team_id="203", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-1",
        competition="WORLD_CUP",
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
    away = Team(external_team_id="18966", name="LAFC", abbreviation="LAFC")
    home = Team(external_team_id="187", name="LA Galaxy", abbreviation="LA")
    game = Game(
        external_game_id="mls-penalties",
        competition="MLS",
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
    alert.event_data = {"status": "in_progress", "period": 5, "clock": "Pens"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject == "Penalty kicks · LAFC 1–1 LA"
    assert "Penalty kicks are underway · LAFC 1–1 LA" in text_body
    assert "Penalties" in text_body
    assert "teamlogos/soccer/500/18966.png" in html_body
    assert "teamlogos/soccer/500/187.png" in html_body


def test_la_liga_game_start_uses_club_logos_and_kickoff_copy():
    away = Team(external_team_id="86", name="Real Madrid", abbreviation="RMA")
    home = Team(external_team_id="83", name="Barcelona", abbreviation="BAR")
    game = Game(
        external_game_id="la-liga-1",
        competition="LA_LIGA",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=0,
        away_score=0,
        period=1,
        clock="2'",
    )
    alert = _mk_alert("game_start")

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject.startswith("Kickoff · RMA @ BAR")
    assert "Kickoff is live now" in text_body
    assert "teamlogos/soccer/500/86.png" in html_body
    assert "teamlogos/soccer/500/83.png" in html_body


def test_premier_competition_game_start_uses_club_logos_and_kickoff_copy():
    away = Team(
        external_team_id="364", name="Liverpool",
        abbreviation="LIV",
    )
    home = Team(
        external_team_id="359", name="Arsenal",
        abbreviation="ARS",
    )
    game = Game(
        external_game_id="premier-competition-1",
        competition="PREMIER_LEAGUE",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=0,
        away_score=0,
        period=1,
        clock="2'",
    )
    alert = _mk_alert("game_start")

    subject = build_alert_subject(alert, game, home, away)
    text_body, html_body = build_alert_email_content(alert, game, home, away)

    assert subject.startswith("Kickoff · LIV @ ARS")
    assert "Kickoff is live now" in text_body
    assert "teamlogos/soccer/500/364.png" in html_body
    assert "teamlogos/soccer/500/359.png" in html_body


def test_world_cup_score_changed_uses_inferred_goal_copy_from_metadata():
    away = Team(external_team_id="203", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-2",
        competition="WORLD_CUP",
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
    alert.event_data = {
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
    away = Team(external_team_id="203", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-3",
        competition="WORLD_CUP",
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
    alert.event_data = {
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
    away = Team(external_team_id="203", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-4",
        competition="WORLD_CUP",
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
    alert.event_data = {"status": "in_progress", "period": 2, "clock": "46'"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Second half · MEX 0–0 USA"
    assert "Second half is live now · MEX 0–0 USA" in text_body
    assert "46'" in text_body


def test_world_cup_extra_time_start_uses_literal_copy():
    away = Team(external_team_id="203", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-extra-time",
        competition="WORLD_CUP",
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
    alert.event_data = {"status": "in_progress", "period": 3, "clock": "91'"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Extra time · MEX 2–2 USA"
    assert "Extra time is live now · MEX 2–2 USA" in text_body
    assert "91'" in text_body


def test_world_cup_penalty_kicks_uses_anticipatory_copy():
    away = Team(external_team_id="203", name="Mexico", abbreviation="MEX")
    home = Team(external_team_id="660", name="United States", abbreviation="USA")
    game = Game(
        external_game_id="world-cup-5",
        competition="WORLD_CUP",
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
    alert.event_data = {"status": "in_progress", "period": 3, "clock": "117'"}

    subject = build_alert_subject(alert, game, home, away)
    text_body, _ = build_alert_email_content(alert, game, home, away)

    assert subject == "Penalty kicks likely soon · MEX 1–1 USA"
    assert "Match is still tied deep in extra time · MEX 1–1 USA" in text_body
    assert "117'" in text_body
