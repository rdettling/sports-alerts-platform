import { describe, expect, it } from "vitest";

import type { Game } from "../../../../shared/api";
import { gameStatusLabel } from "./games-view-utils";

function makeGame(overrides: Partial<Game>): Game {
  return {
    id: 1,
    external_game_id: "g-1",
    league: "MLB",
    home_team_id: 10,
    away_team_id: 11,
    scheduled_start_time: "2026-05-28T17:10:00Z",
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

describe("gameStatusLabel", () => {
  it("shows live clock/inning for in-progress MLB games", () => {
    const label = gameStatusLabel(
      makeGame({
        status: "in_progress",
        period: 5,
        clock: "Top 5th",
      }),
    );
    expect(label).toBe("Top 5th");
  });

  it("shows final label for completed games", () => {
    const label = gameStatusLabel(
      makeGame({
        status: "final",
        is_final: true,
      }),
    );
    expect(label).toBe("Final");
  });

  it("shows postponed label for postponed games", () => {
    const label = gameStatusLabel(
      makeGame({
        status: "postponed",
        is_final: false,
      }),
    );
    expect(label).toBe("Postponed");
  });
});
