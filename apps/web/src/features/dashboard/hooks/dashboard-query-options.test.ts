import type { Game } from "../../../shared/api";

import { describe, expect, it } from "vitest";

import {
  CATALOG_STALE_TIME_MS,
  competitionsQueryOptions,
  followsQueryOptions,
  gamesQueryOptions,
  gamesFallbackInterval,
  teamsQueryOptions,
} from "./dashboard-query-options";

describe("dashboard queries", () => {
  it("fetches games on mount and leaves ongoing refreshes to the coordinator", () => {
    expect(gamesQueryOptions().refetchInterval).toBeUndefined();
    expect(gamesQueryOptions().staleTime).toBe(0);
    expect(gamesQueryOptions().refetchOnMount).toBe("always");
    expect(gamesQueryOptions().refetchOnWindowFocus).toBe(false);
    expect(gamesQueryOptions().refetchOnReconnect).toBe(false);
    expect(teamsQueryOptions().staleTime).toBe(CATALOG_STALE_TIME_MS);
    expect(teamsQueryOptions().refetchOnWindowFocus).toBe(true);
    expect(competitionsQueryOptions().staleTime).toBe(CATALOG_STALE_TIME_MS);
    expect(competitionsQueryOptions().refetchOnWindowFocus).toBe(true);
    expect(followsQueryOptions("token").refetchInterval).toBeUndefined();
  });
});

const NOW = Date.parse("2026-09-04T12:00:00Z");
function game(overrides: Partial<Game>): Game {
  return {
    status: "scheduled",
    is_final: false,
    scheduled_start_time: new Date(NOW + 3_600_000).toISOString(),
    ...overrides,
  } as Game;
}

describe("gamesFallbackInterval", () => {
  it("uses one minute for live games or an initial load failure", () => {
    expect(gamesFallbackInterval(undefined, NOW)).toBe(60_000);
    expect(gamesFallbackInterval([game({ status: "live" })], NOW)).toBe(60_000);
    expect(gamesFallbackInterval([game({ status: "in_progress" })], NOW)).toBe(60_000);
  });

  it("allows quiet empty, scheduled, and final feeds to sleep between checks", () => {
    expect(gamesFallbackInterval([], NOW)).toBe(30 * 60_000);
    expect(gamesFallbackInterval([game({})], NOW)).toBe(30 * 60_000);
    expect(gamesFallbackInterval([game({ status: "live", is_final: true })], NOW)).toBe(
      30 * 60_000,
    );
  });

  it("checks at the earliest future start without postponing it beyond thirty minutes", () => {
    expect(
      gamesFallbackInterval(
        [
          game({ scheduled_start_time: new Date(NOW + 20 * 60_000).toISOString() }),
          game({ scheduled_start_time: new Date(NOW + 5 * 60_000).toISOString() }),
        ],
        NOW,
      ),
    ).toBe(5 * 60_000);
    expect(
      gamesFallbackInterval(
        [game({ scheduled_start_time: new Date(NOW + 100).toISOString() })],
        NOW,
      ),
    ).toBe(1_000);
  });

  it("does not poll rapidly for overdue or invalid scheduled starts", () => {
    expect(
      gamesFallbackInterval(
        [
          game({ scheduled_start_time: new Date(NOW).toISOString() }),
          game({ scheduled_start_time: new Date(NOW - 60_000).toISOString() }),
          game({ scheduled_start_time: "invalid" }),
        ],
        NOW,
      ),
    ).toBe(30 * 60_000);
  });
});
