import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { listGames, listLeagues } from "../../../shared/api";
import { formatSyncAge } from "../utils/telemetry-format";
import { buildSyncRows } from "../components/games/games-view-utils";

export type HeaderSyncItem = {
  key: string;
  label: string;
  value: string;
  tone: "fresh" | "stale" | "idle";
};

export function useDashboardSyncItems() {
  const { data } = useQuery({
    queryKey: ["dashboard-sync-items"],
    queryFn: async () => {
      const [games, leagues] = await Promise.all([listGames({ includeFinals: true, limit: 200 }), listLeagues()]);
      return { games, leagues };
    },
    refetchInterval: 120_000,
  });

  return useMemo<HeaderSyncItem[]>(() => {
    const rows = buildSyncRows(data?.games ?? [], data?.leagues.map((item) => item.league) ?? []);
    return rows.map((row) => ({
      key: row.key,
      label: row.key === "catalog" ? "Catalog" : row.label.replace("Live (", "").replace(")", ""),
      value: formatSyncAge(row.lastAt),
      tone: row.tone,
    }));
  }, [data]);
}
