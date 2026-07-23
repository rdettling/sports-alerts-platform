import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useFollowingData } from "./useFollowingData";

vi.mock("../../../shared/api", () => ({
  listFollows: vi.fn(async () => ({
    leagues: [],
    teams: [],
    games: [
      {
        id: 1,
        external_game_id: "old-final",
        league: "MLB",
        home_team_id: 10,
        away_team_id: 11,
        scheduled_start_time: "2026-05-25T01:00:00Z",
        context_label: null,
        status: "final",
        home_score: 5,
        away_score: 3,
        period: 9,
        clock: "Final",
        is_final: true,
        last_ingested_at: "2026-05-25T04:00:00Z",
        odds: null,
      },
      {
        id: 2,
        external_game_id: "recent-final",
        league: "MLB",
        home_team_id: 12,
        away_team_id: 13,
        scheduled_start_time: "2026-05-28T00:00:00Z",
        context_label: null,
        status: "final",
        home_score: 2,
        away_score: 1,
        period: 9,
        clock: "Final",
        is_final: true,
        last_ingested_at: "2026-05-28T03:00:00Z",
        odds: null,
      },
      {
        id: 3,
        external_game_id: "scheduled",
        league: "NBA",
        home_team_id: 14,
        away_team_id: 15,
        scheduled_start_time: "2026-05-29T01:00:00Z",
        context_label: null,
        status: "scheduled",
        home_score: null,
        away_score: null,
        period: null,
        clock: null,
        is_final: false,
        last_ingested_at: "2026-05-28T03:00:00Z",
        odds: null,
      },
    ],
  })),
  listTeams: vi.fn(async () => []),
  listLeagues: vi.fn(async () => [
    { league: "NBA", sport: "basketball", label: "NBA", badge_label: "NBA", alert_types: [], live_sync_interval_seconds: 120, default_test_matchup: ["ATL", "BOS"], is_enabled: true },
    { league: "MLB", sport: "baseball", label: "MLB", badge_label: "MLB", alert_types: [], live_sync_interval_seconds: 300, default_test_matchup: ["MIA", "TOR"], is_enabled: true },
  ]),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useFollowingData", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads following data", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-05-28T12:00:00Z").getTime());
    const { result } = renderHook(() => useFollowingData("token"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.follows.teams).toHaveLength(0);
    expect(result.current.data?.games.map((game) => game.external_game_id)).toEqual(["recent-final", "scheduled"]);
  });
});
