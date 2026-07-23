import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { listGames, listLeagues, type League } from "../../../shared/api";
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
    const leagueItems = data?.leagues ?? [];
    const rows = buildSyncRows(data?.games ?? [], leagueItems);
    const labelByLeague = new Map(leagueItems.map((item) => [item.league, item.label]));
    return rows.map((row) => ({
      key: row.key,
      label: row.key === "catalog" ? "Catalog" : (labelByLeague.get(row.label.replace("Live (", "").replace(")", "") as League) ?? row.label),
      value: formatSyncAge(row.lastAt),
      tone: row.tone,
    }));
  }, [data]);
}
