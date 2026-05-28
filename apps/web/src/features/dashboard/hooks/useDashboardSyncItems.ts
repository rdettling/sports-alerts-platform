import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { listGames } from "../../../shared/api";
import { formatSyncAge } from "../utils/telemetry-format";
import { buildSyncRows } from "../components/games/games-view-utils";

export type HeaderSyncItem = {
  key: string;
  label: string;
  value: string;
  tone: "fresh" | "stale" | "idle";
};

const SYNC_LABEL_BY_ROW_KEY: Record<string, string> = {
  catalog: "Catalog",
  "Live (NBA)": "NBA",
  "Live (MLB)": "MLB",
};

export function useDashboardSyncItems() {
  const { data } = useQuery({
    queryKey: ["dashboard-sync-items"],
    queryFn: async () => listGames({ includeFinals: true, limit: 200 }),
    refetchInterval: 120_000,
  });

  return useMemo<HeaderSyncItem[]>(() => {
    const rows = buildSyncRows(data ?? []);
    return rows.map((row) => ({
      key: row.key,
      label: SYNC_LABEL_BY_ROW_KEY[row.key] ?? row.label,
      value: formatSyncAge(row.lastAt),
      tone: row.tone,
    }));
  }, [data]);
}
