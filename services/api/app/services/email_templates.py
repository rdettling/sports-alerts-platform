from __future__ import annotations

import html
from datetime import datetime, timezone

from app.db.models import Game, SentAlert, Team
from app.services.email_branding import APP_BRAND_NAME

ALERT_LABELS = {
    "game_start": "Game start",
    "close_game_late": "Close game late",
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


def _team_logo_url(team: Team | None, fallback_abbr: str) -> str:
    abbr = (team.abbreviation if team and team.abbreviation else fallback_abbr).strip().lower()
    if not abbr:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr}.png"


def _scoreline(game: Game) -> str:
    if game.away_score is None or game.home_score is None:
        return "—"
    return f"{game.away_score}\u2013{game.home_score}"


def _format_clock(game: Game) -> str:
    raw = (game.clock or "").strip()
    if not raw or raw in {"0", "0.0", "00:00"}:
        return ""
    return raw


def _format_period(game: Game) -> str:
    if game.period is None:
        return ""
    if game.period <= 4:
        return f"Q{game.period}"
    return f"OT{game.period - 4}"


def _primary_status_line(alert: SentAlert, game: Game, away_abbr: str, home_abbr: str) -> str:
    if alert.alert_type == "final_result":
        return f"Final score: {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "game_start":
        return "Tip-off is live now"
    if alert.alert_type == "close_game_late":
        details = [f"{away_abbr} {_scoreline(game)} {home_abbr}"]
        period = _format_period(game)
        clock = _format_clock(game)
        if period:
            details.append(period)
        if clock:
            details.append(f"{clock} left")
        return " \u2022 ".join(details)
    return f"Status: {game.status}"


def build_alert_subject(alert: SentAlert, game: Game, home: Team | None, away: Team | None) -> str:
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    if alert.alert_type == "final_result":
        return f"Final · {away_abbr} {_scoreline(game)} {home_abbr}"
    if alert.alert_type == "game_start":
        return f"Tip-off · {away_abbr} @ {home_abbr}"
    if alert.alert_type == "close_game_late":
        return f"Close game · {away_abbr} {_scoreline(game)} {home_abbr}"
    return f"{ALERT_LABELS.get(alert.alert_type, 'Alert')} · {away_abbr} @ {home_abbr}"


def build_alert_email_content(alert: SentAlert, game: Game, home: Team | None, away: Team | None) -> tuple[str, str]:
    home_name = home.name if home else f"Team {game.home_team_id}"
    away_name = away.name if away else f"Team {game.away_team_id}"
    away_abbr = _team_abbr(away, "AWAY")
    home_abbr = _team_abbr(home, "HOME")
    away_logo = _team_logo_url(away, away_abbr)
    home_logo = _team_logo_url(home, home_abbr)
    away_score = "—" if game.away_score is None else str(game.away_score)
    home_score = "—" if game.home_score is None else str(game.home_score)
    alert_label = ALERT_LABELS.get(alert.alert_type, alert.alert_type.replace("_", " ").title())
    primary_line = _primary_status_line(alert, game, away_abbr, home_abbr)

    details_parts: list[str] = []
    if game.status:
        details_parts.append(game.status.replace("_", " ").title())
    period = _format_period(game)
    if period:
        details_parts.append(period)
    clock = _format_clock(game)
    if clock:
        details_parts.append(f"{clock} left")
    details_line = " \u2022 ".join(details_parts) if details_parts else "Live update"

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
