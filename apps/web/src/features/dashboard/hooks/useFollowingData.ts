import { useQuery } from "@tanstack/react-query";

import { listFollows, listTeams } from "../../../shared/api";

export function useFollowingData(token: string) {
  return useQuery({
    queryKey: ["following-page", token],
    queryFn: async () => {
      const [follows, teams] = await Promise.all([listFollows(token), listTeams()]);
      const sortedGames = [...follows.games].sort(
        (a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime(),
      );
      return { follows, teams, games: sortedGames };
    },
    refetchInterval: 120_000,
  });
}
