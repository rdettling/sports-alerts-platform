import { describe, expect, it } from "vitest";

import { formatGameTime, formatMoneyline, noVigProbabilities } from "./dashboard-ui";

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
      context_label: null,
      status: "scheduled",
      home_score: null,
      away_score: null,
      period: null,
      clock: null,
      is_final: false,
      last_ingested_at: null,
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

  it("formats MLB live game time without NBA OT labels", () => {
    const label = formatGameTime({
      id: 2,
      external_game_id: "b",
      league: "MLB",
      home_team_id: 1,
      away_team_id: 2,
      scheduled_start_time: new Date().toISOString(),
      context_label: null,
      status: "live",
      home_score: 2,
      away_score: 7,
      period: 8,
      clock: "0:00",
      is_final: false,
      last_ingested_at: null,
      odds: null,
    });

    expect(label).toBe("Inning 8");
    expect(label.includes("OT")).toBe(false);
    expect(label).not.toBe("Halftime");
  });

  it("formats World Cup live clock", () => {
    const label = formatGameTime({
      id: 3,
      external_game_id: "c",
      league: "WORLD_CUP",
      home_team_id: 1,
      away_team_id: 2,
      scheduled_start_time: new Date().toISOString(),
      context_label: null,
      status: "live",
      home_score: 1,
      away_score: 0,
      period: 2,
      clock: "67'",
      is_final: false,
      last_ingested_at: null,
      odds: null,
    });

    expect(label).toBe("67'");
  });
});
