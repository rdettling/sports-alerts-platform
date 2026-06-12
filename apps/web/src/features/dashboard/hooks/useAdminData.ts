import { useQuery } from "@tanstack/react-query";

import {
  getOpsAdminOverview,
  getOpsIngestHealth,
  getOpsLeagueSettings,
  getOpsNeonUsage,
  type OpsAdminOverviewWindow,
} from "../../../shared/api";

export function useAdminData(token: string, windowValue: OpsAdminOverviewWindow) {
  return useQuery({
    queryKey: ["admin-page", token, windowValue],
    queryFn: async () => {
      const [overview, ingestHealth, neonUsage, leagueSettings] = await Promise.all([
        getOpsAdminOverview(token, windowValue, { limit: 30 }),
        getOpsIngestHealth(token, 40),
        getOpsNeonUsage(token),
        getOpsLeagueSettings(token),
      ]);
      return { overview, ingestHealth, neonUsage, leagueSettings };
    },
    refetchInterval: 30_000,
  });
}
