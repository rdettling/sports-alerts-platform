import { queryOptions } from "@tanstack/react-query";

import {
  listCompetitions,
  listFollows,
  listGames,
  listTeams,
  type CurrentFollows,
  type Game,
} from "../../../shared/api";

export const MIN_GAME_REFRESH_INTERVAL_MS = 120_000;
export const LIVE_GAME_FALLBACK_INTERVAL_MS = 10 * 60 * 1_000;
export const GAME_MAINTENANCE_REFETCH_INTERVAL_MS = 12 * 60 * 60 * 1_000;
const SCHEDULED_GAME_OVERDUE_WINDOW_MS = 2 * 60 * 60 * 1_000;
const EMPTY_FOLLOWS: CurrentFollows = { teams: [], games: [] };

export const dashboardQueryKeys = {
  games: ["games"] as const,
  teams: ["teams"] as const,
  competitions: ["competitions"] as const,
  follows: (token: string | null) => ["follows", token ?? "anonymous"] as const,
};

export function gamesFallbackInterval(games: Game[] | undefined, nowMs = Date.now()): number {
  if (
    games?.some(
      (game) => !game.is_final && (game.status === "in_progress" || game.status === "live"),
    )
  ) {
    return LIVE_GAME_FALLBACK_INTERVAL_MS;
  }

  const scheduledStarts = (games ?? [])
    .filter((game) => !game.is_final && game.status === "scheduled")
    .map((game) => new Date(game.scheduled_start_time).getTime())
    .filter(Number.isFinite);

  if (
    scheduledStarts.some(
      (startMs) => startMs <= nowMs && startMs >= nowMs - SCHEDULED_GAME_OVERDUE_WINDOW_MS,
    )
  ) {
    return LIVE_GAME_FALLBACK_INTERVAL_MS;
  }

  const nextStartMs = scheduledStarts
    .filter((startMs) => startMs > nowMs)
    .reduce<number | null>(
      (next, startMs) => (next === null ? startMs : Math.min(next, startMs)),
      null,
    );

  if (nextStartMs === null) return GAME_MAINTENANCE_REFETCH_INTERVAL_MS;
  return Math.min(
    Math.max(nextStartMs - nowMs, MIN_GAME_REFRESH_INTERVAL_MS),
    GAME_MAINTENANCE_REFETCH_INTERVAL_MS,
  );
}

export function gamesQueryOptions() {
  return queryOptions({
    queryKey: dashboardQueryKeys.games,
    queryFn: () => listGames({ includeFinals: true, limit: 500 }),
    staleTime: MIN_GAME_REFRESH_INTERVAL_MS,
    refetchOnWindowFocus: false,
  });
}

export function teamsQueryOptions() {
  return queryOptions({
    queryKey: dashboardQueryKeys.teams,
    queryFn: listTeams,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function competitionsQueryOptions() {
  return queryOptions({
    queryKey: dashboardQueryKeys.competitions,
    queryFn: listCompetitions,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function followsQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: dashboardQueryKeys.follows(token),
    queryFn: () => (token ? listFollows(token) : Promise.resolve(EMPTY_FOLLOWS)),
    staleTime: Number.POSITIVE_INFINITY,
  });
}
