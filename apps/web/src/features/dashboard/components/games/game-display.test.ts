import { describe, expect, it } from "vitest";

import { type Game } from "../../../../shared/api";
import { formatGameTime, formatMoneyline } from "./game-display";

function game(overrides: Partial<Game>): Game {
  return {
    id: 1,
    external_game_id: "game",
    league: "NBA",
    home_team_id: 1,
    away_team_id: 2,
    scheduled_start_time: "2026-06-12T20:40:00Z",
    context_label: null,
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

describe("game display utilities", () => {
  it("formats moneyline values", () => {
    expect(formatMoneyline(120)).toBe("+120");
    expect(formatMoneyline(-105)).toBe("-105");
    expect(formatMoneyline(null)).toBe("—");
  });

  it("formats live game clocks by sport", () => {
    expect(
      formatGameTime(game({ league: "MLB", status: "live", period: 8, clock: "0:00" }), "baseball"),
    ).toBe("Inning 8");
    expect(
      formatGameTime(
        game({ league: "WNBA", status: "live", period: 4, clock: "01:12" }),
        "basketball",
      ),
    ).toBe("Q4 01:12");
    expect(
      formatGameTime(
        game({ league: "WORLD_CUP", status: "live", period: 2, clock: "67'" }),
        "soccer",
      ),
    ).toBe("67'");
    expect(formatGameTime(game({ league: "MLS", status: "live", period: 5 }), "soccer")).toBe(
      "Penalties",
    );
  });

  it("formats scheduled games as time only", () => {
    const label = formatGameTime(game({ league: "MLB" }), "baseball");
    expect(label).toMatch(/:\d{2}/);
    expect(label).not.toMatch(/\d+\/\d+/);
  });
});
