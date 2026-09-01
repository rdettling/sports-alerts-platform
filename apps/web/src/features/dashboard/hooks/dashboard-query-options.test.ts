import { describe, expect, it } from "vitest";

import type { Game } from "../../../shared/api";
import {
  CATALOG_STALE_TIME_MS,
  competitionsQueryOptions,
  followsQueryOptions,
  GAME_MAINTENANCE_REFETCH_INTERVAL_MS,
  gamesFallbackInterval,
  gamesQueryOptions,
  LIVE_GAME_FALLBACK_INTERVAL_MS,
  MIN_GAME_REFRESH_INTERVAL_MS,
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
    scheduled_start_time: new Date(NOW + 60 * 60 * 1_000).toISOString(),
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
    ...overrides,
  };
}

describe("gamesFallbackInterval", () => {
  it("uses the ten-minute fallback for live games", () => {
    expect(gamesFallbackInterval([game({ status: "live" })], NOW)).toBe(
      LIVE_GAME_FALLBACK_INTERVAL_MS,
    );
    expect(gamesFallbackInterval([game({ status: "in_progress" })], NOW)).toBe(
      LIVE_GAME_FALLBACK_INTERVAL_MS,
    );
  });

  it("keeps recently started scheduled games hot for two hours", () => {
    expect(
      gamesFallbackInterval(
        [game({ scheduled_start_time: new Date(NOW - 90 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(LIVE_GAME_FALLBACK_INTERVAL_MS);
  });

  it("waits for the next scheduled start without creating a sub-two-minute refresh", () => {
    expect(
      gamesFallbackInterval(
        [game({ scheduled_start_time: new Date(NOW + 30_000).toISOString() })],
        NOW,
      ),
    ).toBe(MIN_GAME_REFRESH_INTERVAL_MS);
    expect(
      gamesFallbackInterval(
        [game({ scheduled_start_time: new Date(NOW + 30 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(30 * 60 * 1_000);
  });

  it("caps long waits at the maintenance interval", () => {
    expect(
      gamesFallbackInterval(
        [game({ scheduled_start_time: new Date(NOW + 24 * 60 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(GAME_MAINTENANCE_REFETCH_INTERVAL_MS);
  });

  it("uses maintenance cadence for overdue, final, and empty collections", () => {
    expect(
      gamesFallbackInterval(
        [game({ scheduled_start_time: new Date(NOW - 3 * 60 * 60 * 1_000).toISOString() })],
        NOW,
      ),
    ).toBe(GAME_MAINTENANCE_REFETCH_INTERVAL_MS);
    expect(gamesFallbackInterval([game({ status: "final", is_final: true })], NOW)).toBe(
      GAME_MAINTENANCE_REFETCH_INTERVAL_MS,
    );
    expect(gamesFallbackInterval([], NOW)).toBe(GAME_MAINTENANCE_REFETCH_INTERVAL_MS);
  });

  it("leaves all refresh timing to the game refresh coordinator", () => {
    expect(gamesQueryOptions().refetchInterval).toBeUndefined();
    expect(gamesQueryOptions().staleTime).toBe(MIN_GAME_REFRESH_INTERVAL_MS);
    expect(gamesQueryOptions().refetchOnWindowFocus).toBe(false);
    expect(teamsQueryOptions().refetchInterval).toBeUndefined();
    expect(teamsQueryOptions().staleTime).toBe(CATALOG_STALE_TIME_MS);
    expect(teamsQueryOptions().refetchOnWindowFocus).toBe(true);
    expect(competitionsQueryOptions().refetchInterval).toBeUndefined();
    expect(competitionsQueryOptions().staleTime).toBe(CATALOG_STALE_TIME_MS);
    expect(competitionsQueryOptions().refetchOnWindowFocus).toBe(true);
    expect(followsQueryOptions("token").refetchInterval).toBeUndefined();
  });
});
