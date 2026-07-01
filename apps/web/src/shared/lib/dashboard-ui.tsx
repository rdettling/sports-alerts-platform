import { useState } from "react";

import { Game, type League, Team } from "../api";
import worldCupMark from "../../assets/world-cup-mark.png";

const GAME_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "Live",
  final: "Final",
  postponed: "Postponed",
};

export const PREFERENCE_LABELS: Record<string, string> = {
  game_start: "Game start",
  close_game_late: "Close game late",
  inning_start: "Inning start",
  second_half_start: "Second half start",
  penalty_kicks: "Penalty kicks",
  score_changed: "Score change",
  final_result: "Final result",
};

export function messageFromUnknown(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

export function leagueLogoUrl(league: string | null | undefined): string | null {
  const normalized = (league || "").toUpperCase();
  if (normalized === "NBA") return "https://cdn.nba.com/logos/leagues/logo-nba-logoman.svg";
  if (normalized === "MLB") return "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg";
  if (normalized === "WORLD_CUP") return worldCupMark;
  return null;
}

export function leagueBadgeLabel(league: string | null | undefined): string {
  const normalized = (league || "").toUpperCase();
  if (normalized === "WORLD_CUP") return "WC";
  return normalized || "N/A";
}

export function liveCadenceLabel(league: League): string {
  if (league === "NBA") return "2m cadence";
  if (league === "MLB") return "5m cadence";
  return "3m cadence";
}

export function liveStaleAfterMinutes(league: League): number {
  if (league === "NBA") return 4;
  if (league === "MLB") return 10;
  return 6;
}

export function scoreSnippet(game: Game): string {
  if (game.home_score === null || game.away_score === null) {
    return "";
  }
  return `${game.away_score}-${game.home_score}`;
}

function teamLogoUrl(team: Team): string {
  const league = (team.league || "").toUpperCase();
  const abbr = team.abbreviation.toLowerCase();
  if (league === "MLB") {
    return `https://a.espncdn.com/i/teamlogos/mlb/500/${abbr}.png`;
  }
  if (league === "NBA") {
    return `https://a.espncdn.com/i/teamlogos/nba/500/${abbr}.png`;
  }
  if (league === "WORLD_CUP") {
    return `https://a.espncdn.com/i/teamlogos/countries/500/${abbr}.png`;
  }
  return "";
}

export function TeamLogo({ team, size = 26 }: { team: Team; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="team-logo-fallback" style={{ width: size, height: size }}>
        {team.abbreviation.slice(0, 2)}
      </span>
    );
  }
  return (
    <img
      className="team-logo"
      src={teamLogoUrl(team)}
      width={size}
      height={size}
      alt={`${team.name} logo`}
      onError={() => setFailed(true)}
    />
  );
}

export function deliveryStatusClass(status: string): string {
  if (status === "sent") return "chip-final";
  if (status === "failed") return "chip-error";
  return "chip-neutral";
}

export function formatTipoff(dateIso: string): string {
  return new Date(dateIso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatPeriod(period: number | null): string {
  if (period === null) {
    return "";
  }
  if (period <= 4) {
    return `Q${period}`;
  }
  return `OT${period - 4}`;
}

function formatBaseballPeriod(period: number | null): string {
  if (period === null || period <= 0) {
    return "";
  }
  return `Inning ${period}`;
}

function formatSoccerPeriod(period: number | null): string {
  if (period === null || period <= 0) {
    return "";
  }
  if (period === 1) {
    return "1H";
  }
  if (period === 2) {
    return "2H";
  }
  return `ET ${period - 2}`;
}

function isClockAtZero(clock: string): boolean {
  return clock === "0" || clock === "0.0" || clock === "00:00" || clock === "0:00";
}

export function formatGameTime(game: Game): string {
  if (game.status === "in_progress" || game.status === "live") {
    const league = (game.league || "").toUpperCase();
    const period =
      league === "MLB" ? formatBaseballPeriod(game.period) : league === "WORLD_CUP" ? formatSoccerPeriod(game.period) : formatPeriod(game.period);
    const clock = (game.clock ?? "").trim();
    if (league !== "MLB" && game.period === 2 && isClockAtZero(clock)) {
      return "Halftime";
    }
    if (league === "WORLD_CUP" && clock.toUpperCase() === "HT") {
      return "Halftime";
    }
    if (league === "WORLD_CUP" && clock) {
      return clock;
    }
    if (league === "MLB" && clock && !isClockAtZero(clock)) {
      return clock;
    }
    if (league === "MLB" && period && isClockAtZero(clock)) {
      return period;
    }
    if (period && clock) {
      return `${period} ${clock}`;
    }
    if (period) {
      return period;
    }
    if (clock) {
      return clock;
    }
  }
  return formatTipoff(game.scheduled_start_time);
}

export function formatMoneyline(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return value > 0 ? `+${value}` : `${value}`;
}

export function oddsOutcomeByTeamSide(game: Game, teamSide: "away" | "home"): number | null {
  const outcome = game.odds?.outcomes.find((item) => item.team_side === teamSide);
  return outcome?.price_american ?? null;
}

export function drawOdds(game: Game): number | null {
  const outcome = game.odds?.outcomes.find((item) => item.outcome_key === "draw");
  return outcome?.price_american ?? null;
}

export function isThreeWayOdds(game: Game): boolean {
  return (game.odds?.outcomes.length ?? 0) >= 3;
}

function impliedProbabilityFromAmericanOdds(odds: number | null): number | null {
  if (odds === null || odds === 0) {
    return null;
  }
  if (odds > 0) {
    return 100 / (odds + 100);
  }
  const absoluteOdds = Math.abs(odds);
  return absoluteOdds / (absoluteOdds + 100);
}

export function noVigProbabilities(game: Game): { home: number; away: number } | null {
  if (!game.odds || game.odds.outcomes.length !== 2) {
    return null;
  }
  const rawHome = impliedProbabilityFromAmericanOdds(oddsOutcomeByTeamSide(game, "home"));
  const rawAway = impliedProbabilityFromAmericanOdds(oddsOutcomeByTeamSide(game, "away"));
  if (rawHome === null || rawAway === null) {
    return null;
  }
  const total = rawHome + rawAway;
  if (total <= 0) {
    return null;
  }
  return {
    home: rawHome / total,
    away: rawAway / total,
  };
}

export function compactStatusText(game: Game): string | null {
  if (game.status === "scheduled") {
    return null;
  }
  const parts = [GAME_STATUS_LABELS[game.status] ?? game.status];
  const score = scoreSnippet(game);
  if (score) {
    parts.push(score);
  }
  return parts.join(" • ");
}

export function isGameActive(game: Game): boolean {
  return !game.is_final && game.status !== "final";
}

export function isRecentlyCompletedGame(game: Game, nowMs: number): boolean {
  if (isGameActive(game)) {
    return false;
  }
  const startedAtMs = new Date(game.scheduled_start_time).getTime();
  return nowMs - startedAtMs <= 24 * 60 * 60 * 1000;
}
