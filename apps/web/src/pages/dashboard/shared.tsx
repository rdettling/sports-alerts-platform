import { useState } from "react";

import { Game, Team } from "../../api";

const GAME_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "Live",
  final: "Final",
  postponed: "Postponed",
};

export const PREFERENCE_LABELS: Record<string, string> = {
  game_start: "Game start",
  close_game_late: "Close game late",
  final_result: "Final result",
};

export const ALERT_TYPE_LABELS: Record<string, string> = {
  game_start: "Game start",
  close_game_late: "Close game late",
  final_result: "Final result",
};

export function messageFromUnknown(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

export function scoreSnippet(game: Game): string {
  if (game.home_score === null || game.away_score === null) {
    return "";
  }
  return `${game.away_score}-${game.home_score}`;
}

function teamLogoUrl(team: Team): string {
  return `https://cdn.nba.com/logos/nba/${team.external_team_id}/global/L/logo.svg`;
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
  return new Date(dateIso).toLocaleString([], { month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function formatMoneyline(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return value > 0 ? `+${value}` : `${value}`;
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
  if (!game.odds) {
    return null;
  }
  const rawHome = impliedProbabilityFromAmericanOdds(game.odds.home_moneyline);
  const rawAway = impliedProbabilityFromAmericanOdds(game.odds.away_moneyline);
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
