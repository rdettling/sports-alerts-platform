import { useQuery } from "@tanstack/react-query";

import { getOpsAdminSummary, type OpsAdminOverviewWindow } from "../../../shared/api";

export function useAdminData(token: string, windowValue: OpsAdminOverviewWindow) {
  return useQuery({
    queryKey: ["admin-page", token, windowValue],
    queryFn: async () => {
      const summary = await getOpsAdminSummary(token, windowValue);
      return { summary };
    },
    placeholderData: (previousData) => previousData,
    refetchInterval: 30_000,
  });
}
