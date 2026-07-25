import { useQuery } from "@tanstack/react-query";

import {
  listFollows,
  listGames,
  listLeagues,
  listTeams,
  type CurrentFollows,
} from "../../../shared/api";

const EMPTY_FOLLOWS: CurrentFollows = { teams: [], games: [] };

export function useGamesData(token: string | null) {
  return useQuery({
    queryKey: ["games-page", token ?? "anonymous"],
    queryFn: async () => {
      const [availableGames, follows, teams, leagues] = await Promise.all([
        listGames({ includeFinals: true, limit: 500 }),
        token ? listFollows(token) : Promise.resolve(EMPTY_FOLLOWS),
        listTeams(),
        listLeagues(),
      ]);

      return {
        games: availableGames,
        follows,
        teams,
        leagues,
      };
    },
    refetchInterval: 120_000,
  });
}
