import { useQuery } from "@tanstack/react-query";

import { listAlertHistory, listAlertPreferences, listTeams, type AlertType } from "../../../shared/api";

export function useAlertsData(token: string, alertTypeFilter: "all" | AlertType, timeFilter: "24h" | "7d" | "all") {
  return useQuery({
    queryKey: ["alerts-page", token, alertTypeFilter, timeFilter],
    queryFn: async () => {
      const [preferenceResponse, historyResponse, history24Response, teamsResponse] = await Promise.all([
        listAlertPreferences(token),
        listAlertHistory(token, {
          alertType: alertTypeFilter === "all" ? undefined : alertTypeFilter,
          sinceHours: timeFilter === "24h" ? 24 : timeFilter === "7d" ? 24 * 7 : undefined,
          limit: 200,
        }),
        listAlertHistory(token, { sinceHours: 24, limit: 200 }),
        listTeams(),
      ]);
      return {
        preferences: preferenceResponse,
        items: historyResponse.items,
        last24hItems: history24Response.items,
        teams: teamsResponse,
      };
    },
    refetchInterval: 120_000,
  });
}
