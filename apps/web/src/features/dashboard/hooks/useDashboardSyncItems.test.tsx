import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useDashboardSyncItems } from "./useDashboardSyncItems";

vi.mock("../../../shared/api", () => ({
  listLeagues: vi.fn(async () => [
    { league: "NBA", label: "NBA", badge_label: "NBA", alert_types: ["game_start", "close_game_late", "final_result"], is_enabled: true },
    { league: "MLB", label: "MLB", badge_label: "MLB", alert_types: ["game_start", "inning_start", "final_result"], is_enabled: true },
    { league: "WORLD_CUP", label: "World Cup", badge_label: "WC", alert_types: ["game_start", "second_half_start", "extra_time_start", "penalty_kicks", "score_changed", "final_result"], is_enabled: true },
  ]),
  listGames: vi.fn(async () => [
    {
      id: 1,
      external_game_id: "g-1",
      league: "NBA",
      home_team_id: 10,
      away_team_id: 11,
      scheduled_start_time: "2026-05-28T01:00:00Z",
      context_label: null,
      status: "scheduled",
      home_score: null,
      away_score: null,
      period: null,
      clock: null,
      is_final: false,
      last_ingested_at: "2026-05-27T20:00:00Z",
      odds: null,
    },
    {
      id: 2,
      external_game_id: "g-2",
      league: "MLB",
      home_team_id: 20,
      away_team_id: 21,
      scheduled_start_time: "2026-05-28T02:00:00Z",
      context_label: null,
      status: "scheduled",
      home_score: null,
      away_score: null,
      period: null,
      clock: null,
      is_final: false,
      last_ingested_at: "2026-05-27T19:00:00Z",
      odds: null,
    },
  ]),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useDashboardSyncItems", () => {
  it("returns canonical sync labels", async () => {
    const { result } = renderHook(() => useDashboardSyncItems(), { wrapper });

    await waitFor(() => expect(result.current.length).toBe(4));

    expect(result.current.map((item) => item.label)).toEqual(["Catalog", "NBA", "MLB", "World Cup"]);
  });
});
