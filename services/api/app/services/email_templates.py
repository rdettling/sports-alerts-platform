from __future__ import annotations

import html
from datetime import datetime, timezone

from app.db.models import Alert, Game, Team
from app.services.email_branding import APP_BRAND_NAME
from app.services.leagues import get_league_profile

ALERT_LABELS = {
    "game_start": "Game start",
    "close_game_late": "Close game late",
    "overtime_start": "Overtime start",
    "inning_start": "Inning start",
    "extra_innings_start": "Extra innings start",
    "second_half_start": "Second half start",
    "extra_time_start": "Extra time start",
    "penalty_kicks": "Penalty kicks",
    "score_changed": "Score change",
    "final_result": "Final result",
}


def build_magic_link_email(magic_link: str, ttl_minutes: int) -> tuple[str, str, str]:
    subject = f"Sign in to {APP_BRAND_NAME}"
    text_body = (
        "Use this one-time link to sign in:\n\n"
        f"{magic_link}\n\n"
        f"This link expires in {ttl_minutes} minutes."
    )
    html_body = f"""<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f3f6fc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#121a2f;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #dbe3f1;border-radius:16px;padding:24px;">
            <tr>
              <td style="font-size:13px;font-weight:700;color:#4d5ddb;letter-spacing:0.4px;text-transform:uppercase;">
                {APP_BRAND_NAME}
              </td>
            </tr>
            <tr>
              <td style="padding-top:10px;font-size:22px;font-weight:750;color:#0f1f42;">
                Sign in securely
              </td>
            </tr>
            <tr>
              <td style="padding-top:8px;font-size:15px;color:#44506b;line-height:1.5;">
                Use your one-time link to continue to your dashboard.
              </td>
            </tr>
            <tr>
              <td style="padding-top:18px;">
                <a href="{html.escape(magic_link)}" style="display:inline-block;background:#173d9f;color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;padding:12px 18px;border-radius:10px;">
                  Open sign-in link
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding-top:14px;font-size:13px;color:#667694;line-height:1.55;">
                This link expires in {ttl_minutes} minutes.<br/>
                If the button does not work, copy and paste this URL:
              </td>
            </tr>
            <tr>
              <td style="padding-top:8px;">
                <div style="word-break:break-all;background:#f7f9ff;border:1px solid #dbe3f1;border-radius:10px;padding:10px 12px;font-size:12px;color:#2c3c61;">
                  {html.escape(magic_link)}
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding-top:18px;font-size:12px;color:#8a96b0;line-height:1.45;">
                If you didn't request this, you can ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return subject, text_body, html_body


def _team_abbr(team: Team | None, fallback: str) -> str:
    return (team.abbreviation if team and team.abbreviation else fallback).upper()


def _normalize_league(game: Game, home: Team | None, away: Team | None) -> str:
    for raw in (game.league, home.league if home else None, away.league if away else None):
        value = (raw or "").strip().upper()
        if value:
            return value
    return "UNKNOWN"


def _sport_for_league(league: str) -> str | None:
    try:
        return get_league_profile(league).sport
    except ValueError:
        return None


def _team_logo_url(team: Team | None, fallback_abbr: str, league: str) -> str:
    if league == "MLS" and team and team.external_team_id:
        return f"https://a.espncdn.com/i/teamlogos/soccer/500/{team.external_team_id}.png"
    abbr = (team.abbreviation if team and team.abbreviation else fallback_abbr).strip().lower()
    if not abbr:
        return ""
    if league in {"NBA", "WNBA"}:
        return f"https://a.espncdn.com/i/teamlogos/{league.lower()}/500/{abbr}.png"
    if league == "MLB":
        return f"https://a.espncdn.com/i/teamlogos/mlb/500/{abbr}.png"
    if league == "WORLD_CUP":
        return f"https://a.espncdn.com/i/teamlogos/countries/500/{abbr}.png"
    return ""


def _scoreline(game: Game) -> str:
    if game.away_score is None or game.home_score is None:
        return "—"
    return f"{game.away_score}\u2013{game.home_score}"


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


def _score_changed_values(alert: Alert, game: Game) -> tuple[int | None, int | None, int | None, int | None, bool, str | None]:
    metadata = _alert_metadata(alert)
    previous_away_score = _metadata_int(metadata, "previous_away_score")
    previous_home_score = _metadata_int(metadata, "previous_home_score")
    new_away_score = _metadata_int(metadata, "new_away_score")
    new_home_score = _metadata_int(metadata, "new_home_score")
    scoring_side = _metadata_text(metadata, "scoring_side")
    is_inferred_goal = bool(metadata.get("is_inferred_goal"))
    return (
        previous_away_score,
        previous_home_score,
        new_away_score if new_away_score is not None else game.away_score,
        new_home_score if new_home_score is not None else game.home_score,
        is_inferred_goal,
        scoring_side,
    )


def _format_clock(game: Game) -> str:
    raw = (game.clock or "").strip()
    if not raw or raw in {"0", "0.0", "00:00"}:
        return ""
    return raw


def _format_period(game: Game, sport: str | None) -> str:
    if sport != "basketball":
        return ""
    if game.period is None:
        return ""
    if game.period <= 4:
        return f"Q{game.period}"
    return f"OT{game.period - 4}"


def _format_period_value(period: int | None, sport: str | None) -> str:
    if period is None:
        return ""
    if sport == "basketball":
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
    status = _metadata_text(metadata, "status") or game.status
    period = _metadata_int(metadata, "period")
    clock = _metadata_text(metadata, "clock") or game.clock

    details_parts: list[str] = []
    if status:
        details_parts.append(status.replace("_", " ").title())
    period_label = _format_period_value(period, sport)
    if period_label:
        details_parts.append(period_label)

    normalized_clock = (clock or "").strip()
    if normalized_clock:
        if sport == "basketball":
            details_parts.append(f"{normalized_clock} left")
        else:
            details_parts.append(normalized_clock)
    return " \u2022 ".join(details_parts) if details_parts else "Live update"


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
        return f"Final score: {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "game_start":
        if sport == "basketball":
            return "Tip-off is live now"
        if sport == "baseball":
            return "First pitch is live now"
        if sport == "soccer":
            return "Kickoff is live now"
        return "Game start is live now"
    if alert.alert_type == "score_changed":
        _, _, new_away_score, new_home_score, is_inferred_goal, scoring_side = _score_changed_values(alert, game)
        scoreline = _scoreline_from_values(new_away_score, new_home_score)
        if is_inferred_goal:
            scorer = away_abbr if scoring_side == "away" else home_abbr if scoring_side == "home" else "A team"
            return f"Goal for {scorer} · {away_abbr} {scoreline} {home_abbr}"
        return f"Score update · {away_abbr} {scoreline} {home_abbr}"
    if alert.alert_type == "second_half_start":
        return f"Second half is live now · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "extra_time_start":
        return f"Extra time is live now · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "penalty_kicks":
        if (game.period or 0) >= 5:
            return f"Penalty kicks are underway · {away_abbr} {_scoreline(game)} {home_abbr}"
        return f"Match is still tied deep in extra time · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "overtime_start":
        return f"{_overtime_label(alert, game, sport)} is live now · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "extra_innings_start":
        return f"{_extra_inning_label(alert, game)} is underway · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "close_game_late":
        details = [f"{away_abbr} {_scoreline(game)} {home_abbr}"]
        period = _format_period(game, sport)
        clock = _format_clock(game)
        if period:
            details.append(period)
        if clock and sport == "basketball":
            details.append(f"{clock} left")
        elif clock and sport == "baseball":
            details.append(clock)
        return " \u2022 ".join(details)
    if alert.alert_type == "inning_start":
        if sport == "baseball":
            inning = game.period or 0
            return f"Inning {inning} started · {away_abbr} {_scoreline(game)} {home_abbr}"
        return f"Live update · {away_abbr} {_scoreline(game)} {home_abbr}"
    return f"Status: {game.status}"


def build_alert_subject(alert: Alert, game: Game, home: Team | None, away: Team | None) -> str:
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    league = _normalize_league(game, home, away)
    sport = _sport_for_league(league)
    if alert.alert_type == "final_result":
        return f"Final · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "game_start":
        if sport == "basketball":
            return f"Tip-off · {away_abbr} @ {home_abbr}"
        if sport == "baseball":
            return f"First pitch · {away_abbr} @ {home_abbr}"
        if sport == "soccer":
            return f"Kickoff · {away_abbr} @ {home_abbr}"
        return f"Game start · {away_abbr} @ {home_abbr}"
    if alert.alert_type == "score_changed":
        _, _, new_away_score, new_home_score, is_inferred_goal, _ = _score_changed_values(alert, game)
        scoreline = _scoreline_from_values(new_away_score, new_home_score)
        prefix = "Goal" if is_inferred_goal else "Score update"
        return f"{prefix} · {away_abbr} {scoreline} {home_abbr}"
    if alert.alert_type == "second_half_start":
        return f"Second half · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "extra_time_start":
        return f"Extra time · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "penalty_kicks":
        if (game.period or 0) >= 5:
            return f"Penalty kicks · {away_abbr} {_scoreline(game)} {home_abbr}"
        return f"Penalty kicks likely soon · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "overtime_start":
        return f"{_overtime_label(alert, game, sport)} · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "extra_innings_start":
        return f"{_extra_inning_label(alert, game)} · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "close_game_late":
        return f"Close game · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "inning_start":
        return f"Inning start · {away_abbr} @ {home_abbr}"
    return f"{ALERT_LABELS.get(alert.alert_type, 'Alert')} · {away_abbr} @ {home_abbr}"


def build_alert_push_content(alert: Alert, game: Game, home: Team | None, away: Team | None) -> tuple[str, str]:
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    league = _normalize_league(game, home, away)
    sport = _sport_for_league(league)
    return (
        build_alert_subject(alert, game, home, away),
        _primary_status_line(alert, game, away_abbr, home_abbr, sport),
    )


def build_alert_email_content(alert: Alert, game: Game, home: Team | None, away: Team | None) -> tuple[str, str]:
    home_name = home.name if home else f"Team {game.home_team_id}"
    away_name = away.name if away else f"Team {game.away_team_id}"
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    league = _normalize_league(game, home, away)
    sport = _sport_for_league(league)
    away_logo = _team_logo_url(away, away_abbr, league)
    home_logo = _team_logo_url(home, home_abbr, league)
    _, _, score_changed_away_score, score_changed_home_score, _, _ = _score_changed_values(alert, game)
    resolved_away_score = score_changed_away_score if alert.alert_type == "score_changed" else game.away_score
    resolved_home_score = score_changed_home_score if alert.alert_type == "score_changed" else game.home_score
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
