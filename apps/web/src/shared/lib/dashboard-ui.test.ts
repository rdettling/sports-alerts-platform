import { describe, expect, it } from "vitest";

import { formatMoneyline, noVigProbabilities } from "./dashboard-ui";

describe("dashboard utilities", () => {
  it("formats moneyline", () => {
    expect(formatMoneyline(120)).toBe("+120");
    expect(formatMoneyline(-105)).toBe("-105");
    expect(formatMoneyline(null)).toBe("—");
  });

  it("computes no-vig probabilities", () => {
    const result = noVigProbabilities({
      id: 1,
      external_game_id: "a",
      league: "nba",
      home_team_id: 1,
      away_team_id: 2,
      scheduled_start_time: new Date().toISOString(),
      status: "scheduled",
      home_score: null,
      away_score: null,
      period: null,
      clock: null,
      is_final: false,
      odds: {
        home_moneyline: -110,
        away_moneyline: 100,
        bookmaker: "x",
        last_update: null,
      },
    });

    expect(result).not.toBeNull();
    expect((result!.home + result!.away).toFixed(5)).toBe("1.00000");
  });
});
