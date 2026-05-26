import { useQuery } from "@tanstack/react-query";

import { listAlertHistory, listFollows, listGames, listTeams } from "../../../shared/api";

export function useGamesData(token: string) {
  return useQuery({
    queryKey: ["games-page", token],
    queryFn: async () => {
      const [availableGames, follows, teams, alerts24h] = await Promise.all([
        listGames({ includeFinals: true, limit: 200 }),
        listFollows(token),
        listTeams(),
        listAlertHistory(token, { sinceHours: 24, limit: 200 }),
      ]);

      return {
        games: availableGames,
        follows,
        teams,
        sentAlerts24h: alerts24h.items.filter((item) => item.delivery_status === "sent").length,
      };
    },
    refetchInterval: 120_000,
  });
}
