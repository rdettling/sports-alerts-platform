import { useQuery } from "@tanstack/react-query";

import { listAlertHistory, listFollows, listGames, listLeagues, listTeams } from "../../../shared/api";

export function useGamesData(token: string) {
  return useQuery({
    queryKey: ["games-page", token],
    queryFn: async () => {
      const [availableGames, follows, teams, alerts24h, leagues] = await Promise.all([
        listGames({ includeFinals: true, limit: 200 }),
        listFollows(token),
        listTeams(),
        listAlertHistory(token, { sinceHours: 24, limit: 200 }),
        listLeagues(),
      ]);

      return {
        games: availableGames,
        follows,
        teams,
        leagues,
        sentAlerts24h: alerts24h.items.filter((item) => item.delivery_status === "sent").length,
      };
    },
    refetchInterval: 120_000,
  });
}
