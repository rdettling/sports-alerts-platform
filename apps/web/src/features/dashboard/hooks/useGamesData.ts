import { useQuery } from "@tanstack/react-query";

import {
  competitionsQueryOptions,
  followsQueryOptions,
  gamesQueryOptions,
  teamsQueryOptions,
} from "./dashboard-query-options";

export function useGamesData(token: string | null) {
  const games = useQuery(gamesQueryOptions());
  const follows = useQuery(followsQueryOptions(token));
  const teams = useQuery(teamsQueryOptions());
  const competitions = useQuery(competitionsQueryOptions());

  return {
    data: {
      games: games.data ?? [],
      follows: follows.data ?? { teams: [], games: [] },
      teams: teams.data ?? [],
      competitions: competitions.data ?? [],
    },
    isLoading: games.isLoading || follows.isLoading || teams.isLoading || competitions.isLoading,
    isSuccess: games.isSuccess && follows.isSuccess && teams.isSuccess && competitions.isSuccess,
    error: games.error ?? follows.error ?? teams.error ?? competitions.error,
  };
}
