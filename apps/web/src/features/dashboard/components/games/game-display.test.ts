import { describe, expect, it } from "vitest";

import { type Game } from "../../../../shared/api";
import { formatGameTime, formatMoneyline } from "./game-display";

function game(overrides: Partial<Game>): Game {
  return {
    id: 1,
    external_game_id: "game",
    competition: "NBA",
    home_team_id: 1,
    away_team_id: 2,
    scheduled_start_time: "2026-06-12T20:40:00Z",
    context_label: null,
    home_team_record: null,
    away_team_record: null,
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

describe("game display utilities", () => {
  it("formats moneyline values", () => {
    expect(formatMoneyline(120)).toBe("+120");
    expect(formatMoneyline(-105)).toBe("-105");
    expect(formatMoneyline(null)).toBe("—");
  });

  it("formats live game clocks by sport", () => {
    expect(
      formatGameTime(
        game({ competition: "MLB", status: "live", period: 8, clock: "0:00" }),
        "baseball",
      ),
    ).toBe("Inning 8");
    expect(
      formatGameTime(
        game({ competition: "WNBA", status: "live", period: 4, clock: "01:12" }),
        "basketball",
      ),
    ).toBe("Q4 01:12");
    expect(
      formatGameTime(
        game({ competition: "NFL", status: "live", period: 4, clock: "04:31" }),
        "football",
      ),
    ).toBe("Q4 04:31");
    expect(
      formatGameTime(
        game({ competition: "NFL", status: "live", period: 2, clock: "0:00" }),
        "football",
      ),
    ).toBe("Halftime");
    expect(
      formatGameTime(
        game({ competition: "NFL", status: "live", period: 5, clock: "08:42" }),
        "football",
      ),
    ).toBe("OT1 08:42");
    expect(
      formatGameTime(
        game({ competition: "WORLD_CUP", status: "live", period: 2, clock: "67'" }),
        "soccer",
      ),
    ).toBe("67'");
    expect(formatGameTime(game({ competition: "MLS", status: "live", period: 5 }), "soccer")).toBe(
      "Penalties",
    );
  });

  it("formats scheduled games as time only", () => {
    const label = formatGameTime(game({ competition: "MLB" }), "baseball");
    expect(label).toMatch(/:\d{2}/);
    expect(label).not.toMatch(/\d+\/\d+/);
  });
});
