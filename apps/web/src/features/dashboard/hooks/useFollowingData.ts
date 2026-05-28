import { useQuery } from "@tanstack/react-query";

import { listFollows, listTeams } from "../../../shared/api";
import { isGameActive, isRecentlyCompletedGame } from "../../../shared/lib/dashboard-ui";

export function useFollowingData(token: string) {
  return useQuery({
    queryKey: ["following-page", token],
    queryFn: async () => {
      const [follows, teams] = await Promise.all([listFollows(token), listTeams()]);
      const nowMs = Date.now();
      const filteredGames = follows.games.filter((game) => isGameActive(game) || isRecentlyCompletedGame(game, nowMs));
      const sortedGames = [...filteredGames].sort(
        (a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime(),
      );
      return { follows, teams, games: sortedGames };
    },
    refetchInterval: 120_000,
  });
}
