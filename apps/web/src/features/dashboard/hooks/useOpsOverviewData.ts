import { useQuery } from "@tanstack/react-query";

import { getOpsAdminOverview, type OpsAdminOverviewWindow } from "../../../shared/api";

export function useOpsOverviewData(token: string, windowValue: OpsAdminOverviewWindow) {
  return useQuery({
    queryKey: ["ops-overview", token, windowValue],
    queryFn: () => getOpsAdminOverview(token, windowValue, { limit: 30 }),
    refetchInterval: 30_000,
  });
}
