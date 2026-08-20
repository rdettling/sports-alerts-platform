import { useQuery } from "@tanstack/react-query";

import {
  listFollows,
  listGames,
  listCompetitions,
  listTeams,
  type CurrentFollows,
} from "../../../shared/api";

const EMPTY_FOLLOWS: CurrentFollows = { teams: [], games: [] };

export function useGamesData(token: string | null) {
  return useQuery({
    queryKey: ["games-page", token ?? "anonymous"],
    queryFn: async () => {
      const [availableGames, follows, teams, competitions] = await Promise.all([
        listGames({ includeFinals: true, limit: 500 }),
        token ? listFollows(token) : Promise.resolve(EMPTY_FOLLOWS),
        listTeams(),
        listCompetitions(),
      ]);

      return {
        games: availableGames,
        follows,
        teams,
        competitions,
      };
    },
    refetchInterval: 120_000,
  });
}
