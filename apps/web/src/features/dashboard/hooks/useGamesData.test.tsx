import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Game } from "../../../shared/api";
import { useGamesData } from "./useGamesData";

const apiMocks = vi.hoisted(() => ({
  listGames: vi.fn(async (): Promise<Game[]> => []),
  listFollows: vi.fn(async () => ({ teams: [], games: [] })),
  listTeams: vi.fn(async () => []),
  listCompetitions: vi.fn(async () => []),
}));

vi.mock("../../../shared/api", () => apiMocks);

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useGamesData", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockClear());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads public data without requesting follows for a guest", async () => {
    const { result } = renderHook(() => useGamesData(null), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    expect(apiMocks.listTeams).toHaveBeenCalledTimes(1);
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).not.toHaveBeenCalled();
    expect(result.current.data?.follows).toEqual({ teams: [], games: [] });
  });

  it("loads follows when authenticated", async () => {
    const { result } = renderHook(() => useGamesData("token"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMocks.listFollows).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).toHaveBeenCalledWith("token");
  });

  it("refetches only games on the live interval", async () => {
    vi.useFakeTimers();
    apiMocks.listGames.mockResolvedValueOnce([
      {
        id: 1,
        external_game_id: "live-game",
        competition: "NBA",
        home_team_id: 1,
        away_team_id: 2,
        scheduled_start_time: "2026-08-29T18:00:00Z",
        context_label: null,
        home_team_record: null,
        away_team_record: null,
        status: "live",
        home_score: 10,
        away_score: 9,
        period: 1,
        clock: "8:00",
        is_final: false,
        last_ingested_at: "2026-08-29T18:10:00Z",
        odds: null,
      },
    ]);

    const { result } = renderHook(() => useGamesData("token"), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isSuccess).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });

    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    expect(apiMocks.listTeams).toHaveBeenCalledTimes(1);
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).toHaveBeenCalledTimes(1);
  });
});
