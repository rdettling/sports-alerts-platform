import { queryOptions } from "@tanstack/react-query";

import {
  getCompetitionVisibility,
  listCompetitions,
  listFollows,
  listGames,
  listTeams,
  type CompetitionVisibility,
  type CurrentFollows,
  type Game,
} from "../../../shared/api";

export const CATALOG_STALE_TIME_MS = 5 * 60 * 1_000;
const EMPTY_FOLLOWS: CurrentFollows = { teams: [], games: [] };
const EMPTY_COMPETITION_VISIBILITY: CompetitionVisibility = { hidden_competitions: [] };

export const dashboardQueryKeys = {
  games: ["games"] as const,
  teams: ["teams"] as const,
  competitions: ["competitions"] as const,
  competitionVisibility: (token: string | null) =>
    ["competition-visibility", token ?? "anonymous"] as const,
  follows: (token: string | null) => ["follows", token ?? "anonymous"] as const,
};

export function gamesFallbackInterval(games: Game[] | undefined, now = Date.now()): number {
  if (!games) return 60_000;

  let interval = 30 * 60_000;
  for (const game of games) {
    if (game.is_final) continue;
    if (game.status === "live" || game.status === "in_progress") return 60_000;
    if (game.status === "scheduled") {
      const untilStart = new Date(game.scheduled_start_time).getTime() - now;
      if (untilStart > 0) interval = Math.min(interval, Math.max(1_000, untilStart));
    }
  }
  return interval;
}

export function gamesQueryOptions() {
  return queryOptions({
    queryKey: dashboardQueryKeys.games,
    queryFn: () => listGames({ includeFinals: true, limit: 500 }),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
  });
}

export function teamsQueryOptions() {
  return queryOptions({
    queryKey: dashboardQueryKeys.teams,
    queryFn: listTeams,
    staleTime: CATALOG_STALE_TIME_MS,
    refetchOnWindowFocus: true,
  });
}

export function competitionsQueryOptions() {
  return queryOptions({
    queryKey: dashboardQueryKeys.competitions,
    queryFn: listCompetitions,
    staleTime: CATALOG_STALE_TIME_MS,
    refetchOnWindowFocus: true,
  });
}

export function competitionVisibilityQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: dashboardQueryKeys.competitionVisibility(token),
    queryFn: () =>
      token ? getCompetitionVisibility(token) : Promise.resolve(EMPTY_COMPETITION_VISIBILITY),
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
