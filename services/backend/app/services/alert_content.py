from __future__ import annotations

import html
from datetime import datetime, timezone

from app.db.models import Alert, Game, Team
from app.services.email_branding import APP_BRAND_NAME
from app.services.competitions import get_competition_profile

ALERT_LABELS = {
    "game_start": "Game start",
    "close_game_late": "Close game late",
    "overtime_start": "Overtime start",
    "inning_start": "Inning start",
    "extra_innings_start": "Extra innings start",
    "second_half_start": "Second half start",
    "extra_time_start": "Extra time start",
    "penalty_kicks": "Penalty kicks",
    "score_changed": "Score update",
    "lead_change": "Lead change",
    "final_result": "Final result",
}


def _team_abbr(team: Team | None, fallback: str) -> str:
    return (team.abbreviation if team and team.abbreviation else fallback).upper()


def _normalize_competition(game: Game) -> str:
    return game.competition.strip().upper() or "UNKNOWN"


def _sport_for_competition(competition: str) -> str | None:
    try:
        return get_competition_profile(competition).sport
    except ValueError:
        return None


def _team_logo_url(team: Team | None, fallback_abbr: str, competition: str) -> str:
    if competition in {"MLS", "LA_LIGA", "PREMIER_LEAGUE"} and team and team.external_team_id:
        return f"https://a.espncdn.com/i/teamlogos/soccer/500/{team.external_team_id}.png"
    if competition == "FBS" and team and team.external_team_id:
        return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team.external_team_id}.png"
    abbr = (team.abbreviation if team and team.abbreviation else fallback_abbr).strip().lower()
    if not abbr:
        return ""
    if competition in {"NBA", "WNBA"}:
        return f"https://a.espncdn.com/i/teamlogos/{competition.lower()}/500/{abbr}.png"
    if competition == "MLB":
        return f"https://a.espncdn.com/i/teamlogos/mlb/500/{abbr}.png"
    if competition == "NFL":
        return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"
    if competition == "WORLD_CUP":
        return f"https://a.espncdn.com/i/teamlogos/countries/500/{abbr}.png"
    return ""


def _scoreline_from_values(away_score: int | None, home_score: int | None) -> str:
    if away_score is None or home_score is None:
        return "—"
    return f"{away_score}\u2013{home_score}"


def _alert_metadata(alert: Alert) -> dict[str, object]:
    return alert.event_data if isinstance(alert.event_data, dict) else {}


def _metadata_int(metadata: dict[str, object], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _metadata_text(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _snapshot_int(
    metadata: dict[str, object],
    key: str,
    fallback: int | None,
) -> int | None:
    if key not in metadata:
        return fallback
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _snapshot_text(
    metadata: dict[str, object],
    key: str,
    fallback: str | None,
) -> str | None:
    if key not in metadata:
        return fallback
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _game_score_values(alert: Alert, game: Game) -> tuple[int | None, int | None]:
    metadata = _alert_metadata(alert)
    return (
        _snapshot_int(metadata, "away_score", game.away_score),
        _snapshot_int(metadata, "home_score", game.home_score),
    )


def _scoreline(alert: Alert, game: Game) -> str:
    away_score, home_score = _game_score_values(alert, game)
    if away_score is None or home_score is None:
        return "—"
    return f"{away_score}\u2013{home_score}"


def _score_event_values(alert: Alert, game: Game) -> tuple[int | None, int | None, int | None, int | None, bool, str | None]:
    metadata = _alert_metadata(alert)
    previous_away_score = _metadata_int(metadata, "previous_away_score")
    previous_home_score = _metadata_int(metadata, "previous_home_score")
    new_away_score = _metadata_int(metadata, "new_away_score")
    new_home_score = _metadata_int(metadata, "new_home_score")
    scoring_side = _metadata_text(metadata, "scoring_side")
    is_inferred_goal = bool(metadata.get("is_inferred_goal"))
    snapshot_away_score, snapshot_home_score = _game_score_values(alert, game)
    return (
        previous_away_score,
        previous_home_score,
        new_away_score if new_away_score is not None else snapshot_away_score,
        new_home_score if new_home_score is not None else snapshot_home_score,
        is_inferred_goal,
        scoring_side,
    )


def _lead_change_text(alert: Alert, away_abbr: str, home_abbr: str) -> str:
    new_leader = _metadata_text(_alert_metadata(alert), "new_leader")
    if new_leader == "away":
        return f"{away_abbr} takes the lead"
    if new_leader == "home":
        return f"{home_abbr} takes the lead"
    if new_leader == "tied":
        return "Game tied"
    return "Lead change"


def _format_period_value(period: int | None, sport: str | None) -> str:
    if period is None:
        return ""
    if sport in {"basketball", "football"}:
        if period <= 4:
            return f"Q{period}"
        return f"OT{period - 4}"
    if sport == "baseball":
        if period <= 0:
            return ""
        return f"Inning {period}"
    if sport == "soccer":
        if period <= 0:
            return ""
        if period == 1:
            return "1H"
        if period == 2:
            return "2H"
        if period >= 5:
            return "Penalties"
        return f"ET {period - 2}"
    return ""


def _event_status_details(alert: Alert, game: Game, sport: str | None) -> str:
    metadata = _alert_metadata(alert)
    status = _snapshot_text(metadata, "status", game.status)
    period = _snapshot_int(metadata, "period", game.period)
    clock = _snapshot_text(metadata, "clock", game.clock)

    details_parts: list[str] = []
    if status:
        details_parts.append(status.replace("_", " ").title())
    period_label = _format_period_value(period, sport)
    if period_label:
        details_parts.append(period_label)

    normalized_clock = (clock or "").strip()
    if normalized_clock:
        if sport in {"basketball", "football"}:
            details_parts.append(f"{normalized_clock} left")
        else:
            details_parts.append(normalized_clock)
    return " \u2022 ".join(details_parts) if details_parts else "Live update"


def _event_timing_details(alert: Alert, game: Game, sport: str | None) -> str:
    metadata = _alert_metadata(alert)
    period = _snapshot_int(metadata, "period", game.period)
    clock = _snapshot_text(metadata, "clock", game.clock)
    details = [_format_period_value(period, sport)]
    if clock and sport in {"basketball", "football"}:
        details.append(f"{clock} left")
    return " \u2022 ".join(detail for detail in details if detail)


def _overtime_label(alert: Alert, game: Game, sport: str | None) -> str:
    period = _metadata_int(_alert_metadata(alert), "period")
    return _format_period_value(period if period is not None else game.period, sport) or "Overtime"


def _extra_inning_label(alert: Alert, game: Game) -> str:
    inning = _metadata_int(_alert_metadata(alert), "period")
    inning = inning if inning is not None else game.period
    if inning is None:
        return "Extra innings"
    last_two_digits = inning % 100
    suffix = "th" if 11 <= last_two_digits <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(inning % 10, "th")
    return f"{inning}{suffix} inning"


def _primary_status_line(
    alert: Alert,
    game: Game,
    away_abbr: str,
    home_abbr: str,
    sport: str | None,
) -> str:
    if alert.alert_type == "final_result":
        return f"Final score: {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "game_start":
        if sport == "basketball":
            return "Tip-off is live now"
        if sport == "baseball":
            return "First pitch is live now"
        if sport == "soccer":
            return "Kickoff is live now"
        if sport == "football":
            return "Kickoff is live now"
        return "Game start is live now"
    if alert.alert_type == "score_changed":
        _, _, new_away_score, new_home_score, is_inferred_goal, scoring_side = _score_event_values(alert, game)
        scoreline = _scoreline_from_values(new_away_score, new_home_score)
        if is_inferred_goal:
            scorer = away_abbr if scoring_side == "away" else home_abbr if scoring_side == "home" else "A team"
            return f"Goal for {scorer} · {away_abbr} {scoreline} {home_abbr}"
        return f"Score update · {away_abbr} {scoreline} {home_abbr}"
    if alert.alert_type == "lead_change":
        _, _, new_away_score, new_home_score, _, _ = _score_event_values(alert, game)
        scoreline = _scoreline_from_values(new_away_score, new_home_score)
        return f"{_lead_change_text(alert, away_abbr, home_abbr)} · {away_abbr} {scoreline} {home_abbr}"
    if alert.alert_type == "second_half_start":
        return f"Second half is live now · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "extra_time_start":
        return f"Extra time is live now · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "penalty_kicks":
        period = _metadata_int(_alert_metadata(alert), "period")
        if (period if period is not None else game.period or 0) >= 5:
            return f"Penalty kicks are underway · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
        return f"Match is still tied deep in extra time · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "overtime_start":
        return f"{_overtime_label(alert, game, sport)} is live now · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "extra_innings_start":
        return f"{_extra_inning_label(alert, game)} is underway · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "close_game_late":
        _, _, away_score, home_score, _, _ = _score_event_values(alert, game)
        details = [f"{away_abbr} {_scoreline_from_values(away_score, home_score)} {home_abbr}"]
        timing = _event_timing_details(alert, game, sport)
        if timing:
            details.append(timing)
        return " \u2022 ".join(details)
    if alert.alert_type == "inning_start":
        if sport == "baseball":
            inning = _metadata_int(_alert_metadata(alert), "period")
            inning = inning if inning is not None else game.period or 0
            return f"Inning {inning} started · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
        return f"Live update · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    return f"Status: {game.status}"


def build_alert_subject(alert: Alert, game: Game, home: Team | None, away: Team | None) -> str:
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    competition = _normalize_competition(game)
    sport = _sport_for_competition(competition)
    if alert.alert_type == "final_result":
        return f"Final · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "game_start":
        if sport == "basketball":
            return f"Tip-off · {away_abbr} @ {home_abbr}"
        if sport == "baseball":
            return f"First pitch · {away_abbr} @ {home_abbr}"
        if sport == "soccer":
            return f"Kickoff · {away_abbr} @ {home_abbr}"
        if sport == "football":
            return f"Kickoff · {away_abbr} @ {home_abbr}"
        return f"Game start · {away_abbr} @ {home_abbr}"
    if alert.alert_type == "score_changed":
        _, _, new_away_score, new_home_score, is_inferred_goal, _ = _score_event_values(alert, game)
        scoreline = _scoreline_from_values(new_away_score, new_home_score)
        prefix = "Goal" if is_inferred_goal else "Score update"
        return f"{prefix} · {away_abbr} {scoreline} {home_abbr}"
    if alert.alert_type == "lead_change":
        _, _, new_away_score, new_home_score, _, _ = _score_event_values(alert, game)
        scoreline = _scoreline_from_values(new_away_score, new_home_score)
        return f"{_lead_change_text(alert, away_abbr, home_abbr)} · {away_abbr} {scoreline} {home_abbr}"
    if alert.alert_type == "second_half_start":
        return f"Second half · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "extra_time_start":
        return f"Extra time · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "penalty_kicks":
        period = _metadata_int(_alert_metadata(alert), "period")
        if (period if period is not None else game.period or 0) >= 5:
            return f"Penalty kicks · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
        return f"Penalty kicks likely soon · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "overtime_start":
        return f"{_overtime_label(alert, game, sport)} · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "extra_innings_start":
        return f"{_extra_inning_label(alert, game)} · {away_abbr} {_scoreline(alert, game)} {home_abbr}"
    if alert.alert_type == "close_game_late":
        _, _, away_score, home_score, _, _ = _score_event_values(alert, game)
        return f"Close game · {away_abbr} {_scoreline_from_values(away_score, home_score)} {home_abbr}"
    if alert.alert_type == "inning_start":
        return f"Inning start · {away_abbr} @ {home_abbr}"
    return f"{ALERT_LABELS.get(alert.alert_type, 'Alert')} · {away_abbr} @ {home_abbr}"


def build_alert_push_content(alert: Alert, game: Game, home: Team | None, away: Team | None) -> tuple[str, str]:
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    competition = _normalize_competition(game)
    sport = _sport_for_competition(competition)
    body = _primary_status_line(alert, game, away_abbr, home_abbr, sport)
    if alert.alert_type == "lead_change" and _alert_metadata(alert).get("covers_close_game_late") is True:
        timing = _event_timing_details(alert, game, sport)
        if timing:
            body = f"{body} \u2022 {timing}"
    return build_alert_subject(alert, game, home, away), body


def build_alert_email_content(alert: Alert, game: Game, home: Team | None, away: Team | None) -> tuple[str, str]:
    home_name = home.name if home else f"Team {game.home_team_id}"
    away_name = away.name if away else f"Team {game.away_team_id}"
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    competition = _normalize_competition(game)
    sport = _sport_for_competition(competition)
    away_logo = _team_logo_url(away, away_abbr, competition)
    home_logo = _team_logo_url(home, home_abbr, competition)
    _, _, event_away_score, event_home_score, _, _ = _score_event_values(alert, game)
    is_score_event = alert.alert_type in {"score_changed", "lead_change", "close_game_late"}
    snapshot_away_score, snapshot_home_score = _game_score_values(alert, game)
    resolved_away_score = event_away_score if is_score_event else snapshot_away_score
    resolved_home_score = event_home_score if is_score_event else snapshot_home_score
    away_score = "—" if resolved_away_score is None else str(resolved_away_score)
    home_score = "—" if resolved_home_score is None else str(resolved_home_score)
    alert_label = ALERT_LABELS.get(alert.alert_type, alert.alert_type.replace("_", " ").title())
    primary_line = _primary_status_line(alert, game, away_abbr, home_abbr, sport)

    details_line = _event_status_details(alert, game, sport)

    sent_at = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p UTC")

    text_body = (
        f"{APP_BRAND_NAME}\n"
        f"{alert_label}\n\n"
        f"{away_abbr} ({away_score}) @ {home_abbr} ({home_score})\n"
        f"{primary_line}\n"
        f"{away_name} at {home_name}\n"
        f"{details_line}\n"
        f"Sent: {sent_at}\n"
    )

    html_body = f"""<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f3f6fc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#121a2f;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #dbe3f1;border-radius:16px;padding:24px;">
            <tr><td style="font-size:13px;font-weight:700;color:#4d5ddb;letter-spacing:0.4px;text-transform:uppercase;">{APP_BRAND_NAME}</td></tr>
            <tr><td style="padding-top:10px;font-size:22px;font-weight:750;color:#0f1f42;">{html.escape(alert_label)}</td></tr>
            <tr>
              <td style="padding-top:14px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #dbe3f1;border-radius:12px;background:#f7f9ff;">
                  <tr>
                    <td width="44%" align="center" style="padding:14px 8px;">
                      <img src="{html.escape(away_logo)}" alt="{html.escape(away_abbr)} logo" width="42" height="42" style="display:block;margin:0 auto 8px auto;" />
                      <div style="font-size:24px;font-weight:800;color:#0f1f42;line-height:1;">{html.escape(away_abbr)}</div>
                      <div style="padding-top:4px;font-size:28px;font-weight:800;color:#0f1f42;line-height:1;">{html.escape(away_score)}</div>
                    </td>
                    <td width="12%" align="center" style="padding:14px 0;font-size:20px;font-weight:700;color:#6b7a90;">@</td>
                    <td width="44%" align="center" style="padding:14px 8px;">
                      <img src="{html.escape(home_logo)}" alt="{html.escape(home_abbr)} logo" width="42" height="42" style="display:block;margin:0 auto 8px auto;" />
                      <div style="font-size:24px;font-weight:800;color:#0f1f42;line-height:1;">{html.escape(home_abbr)}</div>
                      <div style="padding-top:4px;font-size:28px;font-weight:800;color:#0f1f42;line-height:1;">{html.escape(home_score)}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr><td style="padding-top:14px;font-size:17px;font-weight:650;color:#1d2a4d;">{html.escape(primary_line)}</td></tr>
            <tr><td style="padding-top:6px;font-size:15px;color:#5b6784;">{html.escape(away_name)} at {html.escape(home_name)}</td></tr>
            <tr><td style="padding-top:4px;font-size:14px;color:#7c89a8;">{html.escape(details_line)}</td></tr>
            <tr><td style="padding-top:18px;font-size:12px;color:#8a96b0;">Sent {html.escape(sent_at)}</td></tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    return text_body, html_body
