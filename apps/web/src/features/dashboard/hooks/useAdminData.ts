import { useQuery } from "@tanstack/react-query";

import { getOpsAdminOverview, getOpsIngestHealth, getOpsNeonUsage, type OpsAdminOverviewWindow } from "../../../shared/api";

export function useAdminData(token: string, windowValue: OpsAdminOverviewWindow) {
  return useQuery({
    queryKey: ["admin-page", token, windowValue],
    queryFn: async () => {
      const [overview, ingestHealth, neonUsage] = await Promise.all([
        getOpsAdminOverview(token, windowValue, { limit: 30 }),
        getOpsIngestHealth(token, 40),
        getOpsNeonUsage(token),
      ]);
      return { overview, ingestHealth, neonUsage };
    },
    refetchInterval: 30_000,
  });
}
