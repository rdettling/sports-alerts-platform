import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Game } from "../../../shared/api";
import { useGamesData } from "./useGamesData";

const apiMocks = vi.hoisted(() => ({
  listGames: vi.fn(async (): Promise<Game[]> => []),
  listFollows: vi.fn(async () => ({ teams: [], games: [] })),
  listCompetitions: vi.fn(async () => []),
  getCompetitionVisibility: vi.fn(async () => ({ hidden_competitions: [] })),
  subscribeToGameUpdates: vi.fn(),
}));

let streamOpenHandler: (() => void) | null = null;
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
    streamOpenHandler = null;
    apiMocks.listGames.mockReset().mockResolvedValue([]);
    closeGameUpdates.mockClear();
    apiMocks.subscribeToGameUpdates.mockImplementation(
      (handler: () => void, onOpen: () => void) => {
        streamOpenHandler = onOpen;
        gameUpdateHandler = handler;
        return closeGameUpdates;
      },
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("loads public data without requesting follows for a guest", async () => {
    const { result } = renderHook(() => useGamesData(null), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
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

  it("uses a one-minute fallback and refetches only games", async () => {
    vi.useFakeTimers();
    apiMocks.listGames.mockResolvedValueOnce([
      {
        id: 1,
        external_game_id: "live-game",
        competition: "NBA",
        home_team_id: 1,
        away_team_id: 2,
        home_team: {
          id: 1,
          external_team_id: "1",
          sport: "basketball",
          conference: null,
          name: "Home Team",
          abbreviation: "HOME",
        },
        away_team: {
          id: 2,
          external_team_id: "2",
          sport: "basketball",
          conference: null,
          name: "Away Team",
          abbreviation: "AWAY",
        },
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
      await vi.advanceTimersByTimeAsync(60_000 - 1);
    });

    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2);
    });

    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(1);
    expect(apiMocks.listFollows).toHaveBeenCalledTimes(1);
  });

  it("batches events from the first event and spaces subsequent reads", async () => {
    vi.useFakeTimers();
    renderHook(() => useGamesData(null), { wrapper });
    await advance(10_000);
    await act(async () => gameUpdateHandler?.());
    await advance(800);
    await act(async () => gameUpdateHandler?.());
    await advance(199);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    await act(async () => gameUpdateHandler?.());
    await advance(1_999);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    await advance(1);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
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
      document.dispatchEvent(new Event("visibilitychange"));
      gameUpdateHandler?.();
      await vi.advanceTimersByTimeAsync(5 * 60 * 1_000);
    });
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    expect(closeGameUpdates).toHaveBeenCalledTimes(1);

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

  it.each(["event", "open"])("retains an %s arriving during the initial read", async (kind) => {
    vi.useFakeTimers();
    let finish!: (games: Game[]) => void;
    apiMocks.listGames.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    renderHook(() => useGamesData(null), { wrapper });
    await advance(5_000);
    await act(async () => {
      (kind === "open" ? streamOpenHandler : gameUpdateHandler)?.();
    });
    await advance(5_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    await act(async () => finish([]));
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
  });

  it("retains events during a later refresh without overlapping requests", async () => {
    vi.useFakeTimers();
    renderHook(() => useGamesData(null), { wrapper });
    await advance(10_000);
    let finish!: (games: Game[]) => void;
    apiMocks.listGames.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    await act(async () => gameUpdateHandler?.());
    await advance(1_000);
    await act(async () => {
      gameUpdateHandler?.();
      gameUpdateHandler?.();
    });
    await advance(10_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    await act(async () => finish([]));
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
  });

  it("refreshes on initial stream open and subsequent reconnections", async () => {
    vi.useFakeTimers();
    renderHook(() => useGamesData(null), { wrapper });
    await advance(0);
    await act(async () => streamOpenHandler?.());
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    await advance(5_000);
    await act(async () => streamOpenHandler?.());
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
  });

  it("closes offline and deduplicates overlapping return signals", async () => {
    vi.useFakeTimers();
    let online = true;
    vi.spyOn(navigator, "onLine", "get").mockImplementation(() => online);
    renderHook(() => useGamesData(null), { wrapper });
    await advance(0);
    online = false;
    await act(async () => window.dispatchEvent(new Event("offline")));
    expect(closeGameUpdates).toHaveBeenCalledTimes(1);
    await advance(180_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    online = true;
    await act(async () => {
      window.dispatchEvent(new Event("online"));
      window.dispatchEvent(new Event("focus"));
      window.dispatchEvent(new Event("pageshow"));
    });
    await advance(0);
    expect(apiMocks.subscribeToGameUpdates).toHaveBeenCalledTimes(2);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    await advance(100);
    await act(async () => window.dispatchEvent(new Event("focus")));
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
  });

  it("restores a page hidden through pagehide and cleans up timers on unmount", async () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(() => useGamesData(null), { wrapper });
    await advance(0);
    await act(async () => window.dispatchEvent(new Event("pagehide")));
    await advance(120_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    await act(async () => window.dispatchEvent(new Event("pageshow")));
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    await act(async () => gameUpdateHandler?.());
    unmount();
    await advance(120_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    expect(closeGameUpdates).toHaveBeenCalledTimes(2);
  });

  it.each([{ games: [] }, { games: [{ status: "scheduled" }] }])(
    "uses thirty-minute recovery for quiet feeds: $games",
    async ({ games }) => {
      vi.useFakeTimers();
      apiMocks.listGames.mockResolvedValue(games as Game[]);
      renderHook(() => useGamesData(null), { wrapper });
      await advance(29 * 60_000);
      expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
      await advance(60_001);
      expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
      await advance(30 * 60_000 + 1);
      expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
    },
  );

  it("switches to live recovery at a scheduled start, then slows down after the final", async () => {
    vi.useFakeTimers();
    const scheduled = {
      status: "scheduled",
      scheduled_start_time: new Date(Date.now() + 10 * 60_000).toISOString(),
    } as Game;
    const live = { ...scheduled, status: "live" };
    const final = { ...scheduled, status: "final", is_final: true };
    apiMocks.listGames
      .mockResolvedValueOnce([scheduled])
      .mockResolvedValueOnce([live])
      .mockResolvedValue([final]);
    renderHook(() => useGamesData(null), { wrapper });
    await advance(10 * 60_000 - 1);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    await advance(2);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    await advance(60_001);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
    await advance(29 * 60_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
    await advance(60_001);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(4);
  });

  it("still refreshes promptly when an SSE event arrives during a quiet interval", async () => {
    vi.useFakeTimers();
    renderHook(() => useGamesData(null), { wrapper });
    await advance(10 * 60_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    await act(async () => gameUpdateHandler?.());
    await advance(1_000);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
  });

  it("refreshes on remount even when games are already cached", async () => {
    vi.useFakeTimers();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    function cachedWrapper({ children }: { children: React.ReactNode }) {
      return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    }
    const first = renderHook(() => useGamesData(null), { wrapper: cachedWrapper });
    await advance(0);
    first.unmount();
    renderHook(() => useGamesData(null), { wrapper: cachedWrapper });
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
  });

  it("recovers from a quick hide/return even without EventSource support", async () => {
    vi.useFakeTimers();
    let visible = true;
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() =>
      visible ? "visible" : "hidden",
    );
    apiMocks.subscribeToGameUpdates.mockImplementation(() => () => undefined);
    renderHook(() => useGamesData(null), { wrapper });
    await advance(0);
    await act(async () => window.dispatchEvent(new Event("focus")));
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    visible = false;
    await act(async () => document.dispatchEvent(new Event("visibilitychange")));
    await advance(100);
    visible = true;
    await act(async () => document.dispatchEvent(new Event("visibilitychange")));
    await advance(0);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
    await advance(30 * 60_000 + 1);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(4);
  });

  it("rearms fallback after failures without an immediate retry loop", async () => {
    vi.useFakeTimers();
    apiMocks.listGames.mockResolvedValue([{ status: "live" } as Game]);
    apiMocks.listGames.mockRejectedValueOnce(new Error("offline"));
    renderHook(() => useGamesData(null), { wrapper });
    await advance(59_999);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(1);
    await advance(2);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(2);
    apiMocks.listGames.mockRejectedValueOnce(new Error("offline again"));
    await advance(60_001);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(3);
    await advance(60_001);
    expect(apiMocks.listGames).toHaveBeenCalledTimes(4);
  });
});

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
