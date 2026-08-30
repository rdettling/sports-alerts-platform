import { useQuery } from "@tanstack/react-query";

import {
  competitionVisibilityQueryOptions,
  competitionsQueryOptions,
  followsQueryOptions,
  gamesQueryOptions,
  teamsQueryOptions,
} from "./dashboard-query-options";
import { useGameRefresh } from "./useGameRefresh";

export function useGamesData(token: string | null) {
  const games = useQuery(gamesQueryOptions());
  const follows = useQuery(followsQueryOptions(token));
  const teams = useQuery(teamsQueryOptions());
  const competitions = useQuery(competitionsQueryOptions());
  const competitionVisibility = useQuery(competitionVisibilityQueryOptions(token));

  useGameRefresh({
    games: games.data,
    dataUpdatedAt: games.dataUpdatedAt,
    isFetching: games.isFetching,
  });

  return {
    data: {
      games: games.data ?? [],
      follows: follows.data ?? { teams: [], games: [] },
      teams: teams.data ?? [],
      competitions: competitions.data ?? [],
      competitionVisibility: competitionVisibility.data ?? { hidden_competitions: [] },
    },
    isLoading:
      games.isLoading ||
      follows.isLoading ||
      teams.isLoading ||
      competitions.isLoading ||
      competitionVisibility.isLoading,
    isSuccess:
      games.isSuccess &&
      follows.isSuccess &&
      teams.isSuccess &&
      competitions.isSuccess &&
      competitionVisibility.isSuccess,
    error:
      games.error ??
      follows.error ??
      teams.error ??
      competitions.error ??
      competitionVisibility.error,
  };
}
