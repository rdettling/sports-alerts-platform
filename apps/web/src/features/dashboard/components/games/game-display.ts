import { type Game, type Sport } from "../../../../shared/api";

function formatTipoff(dateIso: string): string {
  return new Date(dateIso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatPeriod(period: number | null): string {
  if (period === null) return "";
  return period <= 4 ? `Q${period}` : `OT${period - 4}`;
}

function formatBaseballPeriod(period: number | null): string {
  return period === null || period <= 0 ? "" : `Inning ${period}`;
}

function formatSoccerPeriod(period: number | null): string {
  if (period === null || period <= 0) return "";
  if (period === 1) return "1H";
  if (period === 2) return "2H";
  if (period >= 5) return "Penalties";
  return `ET ${period - 2}`;
}

function isClockAtZero(clock: string): boolean {
  return clock === "0" || clock === "0.0" || clock === "00:00" || clock === "0:00";
}

export function formatGameTime(game: Game, sport: Sport): string {
  if (game.status === "in_progress" || game.status === "live") {
    const period =
      sport === "baseball"
        ? formatBaseballPeriod(game.period)
        : sport === "soccer"
          ? formatSoccerPeriod(game.period)
          : formatPeriod(game.period);
    const clock = (game.clock ?? "").trim();
    if (sport === "basketball" && game.period === 2 && isClockAtZero(clock)) return "Halftime";
    if (sport === "soccer" && clock.toUpperCase() === "HT") return "Halftime";
    if (sport === "soccer" && clock) return clock;
    if (sport === "baseball" && clock && !isClockAtZero(clock)) return clock;
    if (sport === "baseball" && period && isClockAtZero(clock)) return period;
    if (period && clock) return `${period} ${clock}`;
    if (period) return period;
    if (clock) return clock;
  }
  return formatTipoff(game.scheduled_start_time);
}

export function formatGameStatusLabel(
  status: string,
  isFinal: boolean,
  fallbackTime: string,
): string {
  if (status === "in_progress" || status === "live") return fallbackTime || "Live";
  if (status === "postponed") return "Postponed";
  if (status === "final" || isFinal) return "Final";
  return fallbackTime;
}

export function formatMoneyline(value: number | null): string {
  if (value === null) return "—";
  return value > 0 ? `+${value}` : `${value}`;
}

export function oddsOutcomeByTeamSide(game: Game, teamSide: "away" | "home"): number | null {
  return game.odds?.outcomes.find((item) => item.team_side === teamSide)?.price_american ?? null;
}

export function drawOdds(game: Game): number | null {
  return game.odds?.outcomes.find((item) => item.outcome_key === "draw")?.price_american ?? null;
}

export function isThreeWayOdds(game: Game): boolean {
  return (game.odds?.outcomes.length ?? 0) >= 3;
}
