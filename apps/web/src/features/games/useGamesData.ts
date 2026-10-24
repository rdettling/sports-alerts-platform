import { useQuery } from "@tanstack/react-query";

import {
  competitionVisibilityQueryOptions,
  competitionsQueryOptions,
  followsQueryOptions,
  gamesQueryOptions,
  teamsQueryOptions,
} from "../../shared/api/query-options";
import { useGameRefresh } from "./useGameRefresh";

export function useGamesData(token: string | null) {
  const games = useQuery(gamesQueryOptions());
  const teams = useQuery(teamsQueryOptions());
  const follows = useQuery(followsQueryOptions(token));
  const competitions = useQuery(competitionsQueryOptions());
  const competitionVisibility = useQuery(competitionVisibilityQueryOptions(token));

  useGameRefresh();

  return {
    data: {
      games: games.data ?? [],
      teams: teams.data ?? [],
      follows: follows.data ?? { teams: [], games: [] },
      competitions: competitions.data ?? [],
      competitionVisibility: competitionVisibility.data ?? { hidden_competitions: [] },
    },
    isLoading:
      games.isLoading ||
      teams.isLoading ||
      follows.isLoading ||
      competitions.isLoading ||
      competitionVisibility.isLoading,
    isSuccess:
      games.isSuccess &&
      teams.isSuccess &&
      follows.isSuccess &&
      competitions.isSuccess &&
      competitionVisibility.isSuccess,
    error:
      games.error ??
      teams.error ??
      follows.error ??
      competitions.error ??
      competitionVisibility.error,
  };
}
