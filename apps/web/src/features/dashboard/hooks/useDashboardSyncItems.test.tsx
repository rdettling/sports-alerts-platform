import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useDashboardSyncItems } from "./useDashboardSyncItems";

vi.mock("../../../shared/api", () => ({
  listGames: vi.fn(async () => [
    {
      id: 1,
      external_game_id: "g-1",
      league: "NBA",
      home_team_id: 10,
      away_team_id: 11,
      scheduled_start_time: "2026-05-28T01:00:00Z",
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

    await waitFor(() => expect(result.current.length).toBe(3));

    expect(result.current.map((item) => item.label)).toEqual(["Catalog", "NBA", "MLB"]);
  });
});
