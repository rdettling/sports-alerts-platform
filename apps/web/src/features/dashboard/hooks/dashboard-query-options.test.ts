import { describe, expect, it } from "vitest";

import type { Game } from "../../../shared/api";
import {
  competitionsQueryOptions,
  followsQueryOptions,
  GAME_MAINTENANCE_REFETCH_INTERVAL_MS,
  gamesQueryOptions,
  gamesRefetchInterval,
  LIVE_GAME_REFETCH_INTERVAL_MS,
  teamsQueryOptions,
} from "./dashboard-query-options";

const NOW = new Date("2026-08-29T18:00:00Z").getTime();

function game(overrides: Partial<Game> = {}): Game {
  return {
    id: 1,
    external_game_id: "game-1",
    competition: "NBA",
    home_team_id: 1,
    away_team_id: 2,
    scheduled_start_time: new Date(NOW + 60 * 60 * 1_000).toISOString(),
    context_label: null,
    home_team_record: null,
    away_team_record: null,
    status: "scheduled",
    home_score: null,
    away_score: null,
    period: null,
    clock: null,
    is_final: false,
    last_ingested_at: null,
    odds: null,
    ...overrides,
  };
}

describe("gamesRefetchInterval", () => {
  it("uses the existing two-minute cadence for live games", () => {
    expect(gamesRefetchInterval([game({ status: "live" })], NOW)).toBe(
      LIVE_GAME_REFETCH_INTERVAL_MS,
    );
    expect(gamesRefetchInterval([game({ status: "in_progress" })], NOW)).toBe(
      LIVE_GAME_REFETCH_INTERVAL_MS,
    );
  });

  it("keeps recently started scheduled games hot for two hours", () => {
    expect(
      gamesRefetchInterval(
        [game({ scheduled_start_time: new Date(NOW - 90 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(LIVE_GAME_REFETCH_INTERVAL_MS);
  });

  it("waits for the next scheduled start without creating a sub-two-minute refresh", () => {
    expect(
      gamesRefetchInterval(
        [game({ scheduled_start_time: new Date(NOW + 30_000).toISOString() })],
        NOW,
      ),
    ).toBe(LIVE_GAME_REFETCH_INTERVAL_MS);
    expect(
      gamesRefetchInterval(
        [game({ scheduled_start_time: new Date(NOW + 30 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(30 * 60 * 1_000);
  });

  it("caps long waits at the maintenance interval", () => {
    expect(
      gamesRefetchInterval(
        [game({ scheduled_start_time: new Date(NOW + 24 * 60 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(GAME_MAINTENANCE_REFETCH_INTERVAL_MS);
  });

  it("uses maintenance cadence for overdue, final, and empty collections", () => {
    expect(
      gamesRefetchInterval(
        [game({ scheduled_start_time: new Date(NOW - 3 * 60 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(GAME_MAINTENANCE_REFETCH_INTERVAL_MS);
    expect(gamesRefetchInterval([game({ status: "final", is_final: true })], NOW)).toBe(
      GAME_MAINTENANCE_REFETCH_INTERVAL_MS,
    );
    expect(gamesRefetchInterval([], NOW)).toBe(GAME_MAINTENANCE_REFETCH_INTERVAL_MS);
  });

  it("polls only games and keeps background polling disabled", () => {
    expect(gamesQueryOptions().refetchInterval).toBeTypeOf("function");
    expect(gamesQueryOptions().staleTime).toBe(LIVE_GAME_REFETCH_INTERVAL_MS);
    expect(gamesQueryOptions().refetchIntervalInBackground).toBe(false);
    expect(gamesQueryOptions().refetchOnWindowFocus).toBe(true);
    expect(teamsQueryOptions().refetchInterval).toBeUndefined();
    expect(competitionsQueryOptions().refetchInterval).toBeUndefined();
    expect(followsQueryOptions("token").refetchInterval).toBeUndefined();
  });
});
