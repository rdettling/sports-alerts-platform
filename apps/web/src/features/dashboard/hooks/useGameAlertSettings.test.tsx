import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useGameAlertSettings } from "./useGameAlertSettings";

const apiMocks = vi.hoisted(() => ({
  getGameAlertPreferences: vi.fn(),
  updateGameAlertSettings: vi.fn(),
  resetGameAlertSettings: vi.fn(),
}));

vi.mock("../../../shared/api", () => apiMocks);

const game = {
  id: 12,
  external_game_id: "game-12",
  competition: "WNBA" as const,
  home_team_id: 1,
  away_team_id: 2,
  scheduled_start_time: "2026-08-19T20:00:00Z",
  context_label: null,
  home_team_strength: { wins: null, losses: null, ties: null, rank: null },
  away_team_strength: { wins: null, losses: null, ties: null, rank: null },
  broadcast_names: [],
  status: "scheduled",
  home_score: null,
  away_score: null,
  period: null,
  clock: null,
  is_final: false,
  last_ingested_at: null,
  odds: null,
};

const inheritedItem = {
  competition: "WNBA" as const,
  alert_type: "game_start",
  uses_sport_defaults: true,
  is_enabled: true,
  close_game_margin_threshold: null,
  close_game_time_threshold_seconds: null,
  inning_start_threshold: null,
};

describe("useGameAlertSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getGameAlertPreferences.mockResolvedValue({
      game_id: game.id,
      competition: game.competition,
      items: [inheritedItem],
    });
  });

  it("updates and resets local state without refetching", async () => {
    const setError = vi.fn();
    const overridden = { ...inheritedItem, uses_sport_defaults: false, is_enabled: false };
    apiMocks.updateGameAlertSettings.mockResolvedValue(overridden);
    apiMocks.resetGameAlertSettings.mockResolvedValue(inheritedItem);
    const { result } = renderHook(() => useGameAlertSettings("token", setError));

    await act(() => result.current.openGameAlerts(game));
    await act(() =>
      result.current.updateGameAlertSettings(game.id, "game_start", {
        is_enabled: false,
        close_game_margin_threshold: null,
        close_game_time_threshold_seconds: null,
        inning_start_threshold: null,
      }),
    );
    expect(result.current.gameAlertState?.items[0]).toEqual(overridden);
    expect(apiMocks.getGameAlertPreferences).toHaveBeenCalledTimes(1);

    await act(() => result.current.resetGameAlertSettings(game.id, "game_start"));
    expect(result.current.gameAlertState?.items[0]).toEqual(inheritedItem);
    expect(apiMocks.getGameAlertPreferences).toHaveBeenCalledTimes(1);
  });

  it("keeps existing state and reports update and reset failures", async () => {
    const setError = vi.fn();
    apiMocks.updateGameAlertSettings.mockRejectedValue(new Error("Update failed"));
    apiMocks.resetGameAlertSettings.mockRejectedValue(new Error("Reset failed"));
    const { result } = renderHook(() => useGameAlertSettings("token", setError));

    await act(() => result.current.openGameAlerts(game));
    await act(() =>
      result.current.updateGameAlertSettings(game.id, "game_start", {
        is_enabled: false,
        close_game_margin_threshold: null,
        close_game_time_threshold_seconds: null,
        inning_start_threshold: null,
      }),
    );
    expect(result.current.gameAlertState?.items[0]).toEqual(inheritedItem);
    expect(setError).toHaveBeenLastCalledWith("Update failed");

    await act(() => result.current.resetGameAlertSettings(game.id, "game_start"));
    expect(result.current.gameAlertState?.items[0]).toEqual(inheritedItem);
    expect(setError).toHaveBeenLastCalledWith("Reset failed");
  });
});
