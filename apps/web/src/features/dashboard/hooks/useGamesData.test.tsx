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
  getCompetitionVisibility: vi.fn(async () => ({ hidden_competitions: [] })),
  subscribeToGameUpdates: vi.fn(),
}));

let gameUpdateHandler: (() => void) | null = null;
const closeGameUpdates = vi.fn();

vi.mock("../../../shared/api", () => apiMocks);

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useGamesData", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockClear());
    gameUpdateHandler = null;
    closeGameUpdates.mockClear();
    apiMocks.subscribeToGameUpdates.mockImplementation((handler: () => void) => {
      gameUpdateHandler = handler;
      return closeGameUpdates;
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("loads public data without requesting follows for a guest", async () => {
    const { result } = renderHook(() => useGamesData(null), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    expect(apiMocks.listTeams).toHaveBeenCalledTimes(1);
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).not.toHaveBeenCalled();
    expect(apiMocks.getCompetitionVisibility).not.toHaveBeenCalled();
    expect(result.current.data?.follows).toEqual({ teams: [], games: [] });
    expect(result.current.data?.competitionVisibility).toEqual({ hidden_competitions: [] });
  });

  it("loads follows when authenticated", async () => {
    const { result } = renderHook(() => useGamesData("token"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMocks.listFollows).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).toHaveBeenCalledWith("token");
    expect(apiMocks.getCompetitionVisibility).toHaveBeenCalledWith("token");
  });

  it("uses a ten-minute fallback and refetches only games", async () => {
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
        home_team_strength: { wins: null, losses: null, ties: null, rank: null },
        away_team_strength: { wins: null, losses: null, ties: null, rank: null },
        broadcast_names: [],
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
      await vi.advanceTimersByTimeAsync(10 * 60 * 1_000 - 1);
    });

    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    expect(apiMocks.listTeams).toHaveBeenCalledTimes(1);
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).toHaveBeenCalledTimes(1);
  });

  it("coalesces SSE events behind the hard two-minute request limit", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useGamesData(null), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isSuccess).toBe(true);
    expect(gameUpdateHandler).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
      gameUpdateHandler?.();
      gameUpdateHandler?.();
      await vi.advanceTimersByTimeAsync(89_999);
    });
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    expect(apiMocks.listTeams).toHaveBeenCalledTimes(1);
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).not.toHaveBeenCalled();
  });

  it("defers hidden-tab events and refreshes once on return", async () => {
    vi.useFakeTimers();
    let visibility: DocumentVisibilityState = "visible";
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);

    const { result } = renderHook(() => useGamesData(null), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isSuccess).toBe(true);

    visibility = "hidden";
    await act(async () => {
      gameUpdateHandler?.();
      await vi.advanceTimersByTimeAsync(5 * 60 * 1_000);
    });
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);

    visibility = "visible";
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
  });

  it("closes the SSE subscription when the Games screen unmounts", async () => {
    const { result, unmount } = renderHook(() => useGamesData(null), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    unmount();

    expect(closeGameUpdates).toHaveBeenCalledTimes(1);
  });
});
