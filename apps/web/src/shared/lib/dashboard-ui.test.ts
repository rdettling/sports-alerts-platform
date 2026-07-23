import { describe, expect, it } from "vitest";

import {
  formatGameTime,
  formatMoneyline,
  leagueLogoUrl,
  noVigProbabilities,
} from "./dashboard-ui";

describe("dashboard utilities", () => {
  it("formats moneyline", () => {
    expect(formatMoneyline(120)).toBe("+120");
    expect(formatMoneyline(-105)).toBe("-105");
    expect(formatMoneyline(null)).toBe("—");
  });

  it("uses the MLS crest instead of a text fallback", () => {
    expect(leagueLogoUrl("MLS")).toBe(
      "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg",
    );
  });

  it("computes no-vig probabilities", () => {
    const result = noVigProbabilities({
      id: 1,
      external_game_id: "a",
      league: "NBA",
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
        market: "h2h",
        bookmaker: "x",
        last_update: null,
        outcomes: [
          { outcome_key: "away", outcome_label: "Away", price_american: 100, team_side: "away" },
          { outcome_key: "home", outcome_label: "Home", price_american: -110, team_side: "home" },
        ],
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
    }, "baseball");

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
    }, "soccer");

    expect(label).toBe("67'");
  });

  it("formats an MLS shootout without an extra-time label", () => {
    const label = formatGameTime({
      id: 6,
      external_game_id: "mls-shootout",
      league: "MLS",
      home_team_id: 1,
      away_team_id: 2,
      scheduled_start_time: new Date().toISOString(),
      context_label: null,
      status: "live",
      home_score: 1,
      away_score: 1,
      period: 5,
      clock: null,
      is_final: false,
      last_ingested_at: null,
      odds: null,
    }, "soccer");

    expect(label).toBe("Penalties");
  });

  it("formats scheduled games as time only", () => {
    const label = formatGameTime({
      id: 5,
      external_game_id: "e",
      league: "MLB",
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
    }, "baseball");

    expect(label).toMatch(/:\d{2}/);
    expect(label).not.toMatch(/\d+\/\d+/);
  });

  it("skips no-vig probabilities for three-way odds", () => {
    const result = noVigProbabilities({
      id: 4,
      external_game_id: "d",
      league: "WORLD_CUP",
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
        market: "h2h",
        bookmaker: "x",
        last_update: null,
        outcomes: [
          { outcome_key: "mex", outcome_label: "Mexico", price_american: 180, team_side: "away" },
          { outcome_key: "draw", outcome_label: "Draw", price_american: 210, team_side: null },
          { outcome_key: "usa", outcome_label: "United States", price_american: 160, team_side: "home" },
        ],
      },
    });

    expect(result).toBeNull();
  });
});
