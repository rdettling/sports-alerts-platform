import { describe, expect, it } from "vitest";

import type { Game } from "../../../../shared/api";
import {
  americanOddsImpliedProbability,
  baseballHalfInningsRemaining,
  baseballWatchabilityScore,
  basketballGameSecondsRemaining,
  basketballRegulationSecondsRemaining,
  basketballWatchabilityScore,
  combinedTeamStrengthFactor,
  footballRegulationSecondsRemaining,
  footballWatchabilityScore,
  liveWatchabilityScore,
  marketCompetitivenessFactor,
  matchupQualityFactor,
  normalizeProbabilities,
  pregameFavoriteNonWinProbability,
  pregameMarketCompetitiveness,
  pregameWatchabilityScore,
  soccerRegulationMinutesRemaining,
  soccerWatchabilityScore,
  teamStrengthFactor,
} from "./game-watchability";
import { sortGames } from "./games-view-utils";

function makeGame(overrides: Partial<Game> = {}): Game {
  return {
    id: 1,
    external_game_id: "g-1",
    competition: "MLB",
    home_team_id: 10,
    away_team_id: 11,
    home_team: {
      id: 10,
      external_team_id: "10",
      sport: "basketball",
      conference: null,
      name: "Home Team",
      abbreviation: "HOME",
    },
    away_team: {
      id: 11,
      external_team_id: "11",
      sport: "basketball",
      conference: null,
      name: "Away Team",
      abbreviation: "AWAY",
    },
    scheduled_start_time: "2026-05-28T17:10:00Z",
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

function withOdds(
  game: Game,
  prices: readonly (number | null)[],
  lastUpdate = new Date(Date.parse(game.scheduled_start_time) - 60 * 60 * 1000).toISOString(),
): Game {
  const outcomeKeys = prices.length === 3 ? ["away", "draw", "home"] : ["away", "home"];
  const outcomes: NonNullable<Game["odds"]>["outcomes"] = prices.map((price, index) => ({
    outcome_key: outcomeKeys[index],
    outcome_label: outcomeKeys[index],
    price_american: price,
    team_side: outcomeKeys[index] === "draw" ? null : (outcomeKeys[index] as "away" | "home"),
  }));
  return {
    ...game,
    odds: { bookmaker: "Synthetic", last_update: lastUpdate, outcomes },
  };
}

describe("football live calculations", () => {
  it("calculates regulation time remaining across quarters, halftime, and overtime", () => {
    const cases: Array<[Partial<Game>, number]> = [
      [{ competition: "NFL", status: "in_progress", period: 1, clock: "15:00" }, 3600],
      [{ competition: "NFL", status: "in_progress", period: 2, clock: "0:00" }, 1800],
      [{ competition: "FBS", status: "live", period: 4, clock: "02:30" }, 150],
      [{ competition: "NFL", status: "in_progress", period: 5, clock: null }, 0],
    ];
    cases.forEach(([overrides, expected]) => {
      expect(footballRegulationSecondsRemaining(makeGame(overrides))).toBe(expected);
    });
  });

  it("rejects missing, malformed, non-live, and non-football state", () => {
    const cases: Partial<Game>[] = [
      { competition: "NFL", status: "in_progress", period: 4, clock: "2 minutes" },
      { competition: "NFL", status: "in_progress", period: 4, clock: "16:00" },
      { competition: "NFL", status: "scheduled", period: 4, clock: "02:00" },
      { competition: "MLB", status: "in_progress", period: 4, clock: "02:00" },
    ];
    cases.forEach((overrides) => {
      expect(footballRegulationSecondsRemaining(makeGame(overrides))).toBeNull();
    });
  });

  it("combines calibrated margin and progress factors", () => {
    const cases: Array<[Partial<Game>, number]> = [
      [
        {
          competition: "NFL",
          status: "in_progress",
          period: 1,
          clock: "15:00",
          home_score: 0,
          away_score: 0,
        },
        45,
      ],
      [
        {
          competition: "NFL",
          status: "in_progress",
          period: 4,
          clock: "04:00",
          home_score: 24,
          away_score: 21,
        },
        92,
      ],
      [
        {
          competition: "FBS",
          status: "in_progress",
          period: 3,
          clock: "07:30",
          home_score: 21,
          away_score: 14,
        },
        71,
      ],
      [
        {
          competition: "NFL",
          status: "in_progress",
          period: 5,
          home_score: 24,
          away_score: 24,
        },
        100,
      ],
      [
        {
          competition: "NFL",
          status: "in_progress",
          period: 4,
          clock: "00:30",
          home_score: 35,
          away_score: 10,
        },
        0,
      ],
    ];
    cases.forEach(([overrides, expected]) => {
      expect(footballWatchabilityScore(makeGame(overrides))).toBe(expected);
    });
  });
});

describe("football watchability calibration", () => {
  const eliteStrength = { wins: 10, losses: 0, ties: 0, rank: null };
  const neutralStrength = { wins: null, losses: null, ties: null, rank: null };

  function liveGame(
    id: number,
    period: number,
    clock: string,
    margin: number,
    elite = false,
  ): Game {
    return makeGame({
      id,
      external_game_id: `football-live-${id}`,
      competition: "NFL",
      scheduled_start_time: "2026-09-06T17:00:00Z",
      status: "in_progress",
      period,
      clock,
      home_score: margin,
      away_score: 0,
      home_team_strength: elite ? eliteStrength : neutralStrength,
      away_team_strength: elite ? eliteStrength : neutralStrength,
    });
  }

  function rankedGame(id: number, homeRank: number, awayRank: number, start: string): Game {
    return makeGame({
      id,
      external_game_id: `football-pregame-${id}`,
      competition: "FBS",
      scheduled_start_time: start,
      home_team_strength: { wins: 0, losses: 0, ties: 0, rank: homeRank },
      away_team_strength: { wins: 0, losses: 0, ties: 0, rank: awayRank },
    });
  }

  it("matches the calibrated live choices", () => {
    const choices: Array<[Game, Game, number]> = [
      [liveGame(101, 3, "06:00", 0), liveGame(102, 4, "06:00", 7, true), 102],
      [liveGame(103, 2, "10:00", 3), liveGame(104, 4, "02:00", 14), 103],
      [liveGame(105, 2, "00:00", 0, true), liveGame(106, 4, "01:00", 8), 106],
      [liveGame(107, 1, "12:00", 0), liveGame(108, 4, "05:00", 17, true), 107],
    ];
    choices.forEach(([a, b, expectedId]) => {
      expect(sortGames([a, b], "watchability")[0].id).toBe(expectedId);
    });
  });

  it("prefers two strong scheduled teams and ignores kickoff proximity", () => {
    const firstVsTwentyFifth = rankedGame(109, 1, 25, "2026-09-06T17:00:00Z");
    const tenthVsEleventh = rankedGame(110, 10, 11, "2026-09-06T17:00:00Z");
    expect(sortGames([firstVsTwentyFifth, tenthVsEleventh], "watchability")[0].id).toBe(110);

    const strongerLater = rankedGame(113, 2, 4, "2026-09-06T21:00:00Z");
    const weakerSooner = rankedGame(114, 15, 18, "2026-09-06T17:10:00Z");
    expect(sortGames([weakerSooner, strongerLater], "watchability")[0].id).toBe(113);

    const identicalLater = rankedGame(115, 8, 9, "2026-09-06T21:00:00Z");
    const identicalSooner = rankedGame(116, 8, 9, "2026-09-06T17:10:00Z");
    expect(
      sortGames([identicalSooner, identicalLater], "watchability").map(({ id }) => id),
    ).toEqual([116, 115]);
  });

  it("prefers two 9-1 teams over an undefeated mismatch", () => {
    const twoNineAndOneTeams = makeGame({
      id: 111,
      competition: "NFL",
      home_team_strength: { wins: 9, losses: 1, ties: 0, rank: null },
      away_team_strength: { wins: 9, losses: 1, ties: 0, rank: null },
    });
    const undefeatedMismatch = makeGame({
      id: 112,
      competition: "NFL",
      home_team_strength: { wins: 10, losses: 0, ties: 0, rank: null },
      away_team_strength: { wins: 4, losses: 6, ties: 0, rank: null },
    });
    expect(sortGames([undefeatedMismatch, twoNineAndOneTeams], "watchability")[0].id).toBe(111);
  });
});

describe("baseball live calculations", () => {
  it("calculates remaining half-innings through regulation and extras", () => {
    const cases: Array<[Partial<Game>, number]> = [
      [{ status: "in_progress", period: 1, clock: "Top 1st" }, 18],
      [{ status: "in_progress", period: 5, clock: "Bottom 5th" }, 9],
      [{ status: "live", period: 9, clock: "Top 9th" }, 2],
      [{ status: "in_progress", period: 9, clock: "Rain Delay, Bottom 9th" }, 1],
      [{ status: "in_progress", period: 10, clock: "Top 10th" }, 0],
    ];
    cases.forEach(([overrides, expected]) => {
      expect(baseballHalfInningsRemaining(makeGame(overrides))).toBe(expected);
    });
  });

  it("uses the inning as an approximation when half-inning detail is unavailable", () => {
    expect(
      baseballHalfInningsRemaining(makeGame({ status: "in_progress", period: 7, clock: null })),
    ).toBe(6);
    expect(
      baseballHalfInningsRemaining(makeGame({ status: "scheduled", period: 7, clock: "Top 7th" })),
    ).toBeNull();
    expect(
      baseballHalfInningsRemaining(
        makeGame({ competition: "NFL", status: "in_progress", period: 4, clock: "02:00" }),
      ),
    ).toBeNull();
  });

  it("combines run margin with increasing late-inning urgency", () => {
    const cases: Array<[Partial<Game>, number]> = [
      [{ status: "in_progress", period: 1, clock: "Top 1st", home_score: 0, away_score: 0 }, 55],
      [{ status: "in_progress", period: 9, clock: "Bottom 9th", home_score: 4, away_score: 3 }, 93],
      [{ status: "in_progress", period: 8, clock: "Bottom 8th", home_score: 5, away_score: 3 }, 74],
      [{ status: "in_progress", period: 10, clock: "Top 10th", home_score: 5, away_score: 5 }, 100],
      [{ status: "in_progress", period: 9, clock: "Bottom 9th", home_score: 8, away_score: 2 }, 0],
    ];
    cases.forEach(([overrides, expected]) => {
      expect(baseballWatchabilityScore(makeGame(overrides))).toBe(expected);
    });
  });
});

describe("team quality", () => {
  it("uses records with neutral missing or 0-0 strength", () => {
    expect(teamStrengthFactor({ wins: 6, losses: 2, ties: 2, rank: null }, "NFL")).toBeCloseTo(0.7);
    expect(teamStrengthFactor({ wins: null, losses: null, ties: null, rank: null }, "NBA")).toBe(
      0.5,
    );
    expect(teamStrengthFactor({ wins: 0, losses: 0, ties: 0, rank: null }, "MLS")).toBe(0.5);
  });

  it("prioritizes FBS poll rankings and caps unranked strength", () => {
    expect(teamStrengthFactor({ wins: 1, losses: 8, ties: 0, rank: 1 }, "FBS")).toBe(1);
    expect(teamStrengthFactor({ wins: 1, losses: 8, ties: 0, rank: 25 }, "FBS")).toBe(0.75);
    expect(teamStrengthFactor({ wins: 10, losses: 0, ties: 0, rank: null }, "FBS")).toBe(0.7);
  });

  it("keeps live matchup quality distinct from combined pregame team strength", () => {
    const game = makeGame({
      competition: "NBA",
      home_team_strength: { wins: 8, losses: 2, ties: null, rank: null },
      away_team_strength: { wins: 6, losses: 4, ties: null, rank: null },
    });
    expect(matchupQualityFactor(game)).toBeCloseTo(0.685);
    expect(combinedTeamStrengthFactor(game)).toBeCloseTo(0.7);
    expect(pregameWatchabilityScore(game)).toBeCloseTo(76);

    const rankedFbsMatchup = makeGame({
      competition: "FBS",
      home_team_strength: { wins: 1, losses: 8, ties: 0, rank: 1 },
      away_team_strength: { wins: 10, losses: 0, ties: 0, rank: null },
    });
    expect(combinedTeamStrengthFactor(rankedFbsMatchup)).toBeCloseTo(0.85);
    expect(pregameWatchabilityScore(rankedFbsMatchup)).toBeCloseTo(88);
  });
});

describe("pregame market competitiveness", () => {
  it("converts positive and negative American odds to implied probabilities", () => {
    expect(americanOddsImpliedProbability(150)).toBeCloseTo(0.4);
    expect(americanOddsImpliedProbability(-200)).toBeCloseTo(2 / 3);
  });

  it("removes vig by normalizing implied probabilities", () => {
    const implied = [-110, -110].map((price) => americanOddsImpliedProbability(price));
    expect(implied.every((probability) => probability !== null)).toBe(true);

    const normalized = normalizeProbabilities(implied as number[]);
    expect(normalized).not.toBeNull();
    expect(normalized?.reduce((sum, probability) => sum + probability, 0)).toBeCloseTo(1);
    expect(normalized).toEqual([0.5, 0.5]);
  });

  it("scores balanced and heavily favored two-way markets", () => {
    expect(marketCompetitivenessFactor([-110, -110])).toBe(1);
    expect(marketCompetitivenessFactor([-1000, 650])).toBeCloseTo(0.255814);
  });

  it("scores balanced and skewed three-way soccer markets", () => {
    expect(marketCompetitivenessFactor([200, 200, 200])).toBe(1);
    expect(marketCompetitivenessFactor([-300, 450, 800])).toBeCloseTo(0.421488);
  });

  it("uses the chance the favorite does not win across two- and three-way markets", () => {
    const twoWay = withOdds(makeGame({ competition: "NBA" }), [-400, 400]);
    expect(pregameFavoriteNonWinProbability(twoWay)).toBeCloseTo(0.2);

    const threeWay = withOdds(makeGame({ competition: "PREMIER_LEAGUE" }), [-400, 500, 900]);
    expect(pregameFavoriteNonWinProbability(threeWay)).toBeCloseTo(0.25);
  });

  it("rejects missing, stale, malformed, incomplete, and null-priced odds", () => {
    const game = makeGame({ competition: "NBA" });
    expect(pregameMarketCompetitiveness(game)).toBeNull();
    expect(pregameFavoriteNonWinProbability(game)).toBeNull();
    expect(pregameWatchabilityScore(game)).toBe(60);

    const nullPrice = withOdds(game, [null, -110]);
    expect(pregameMarketCompetitiveness(nullPrice)).toBeNull();
    expect(pregameWatchabilityScore(nullPrice)).toBe(60);

    const incomplete = withOdds(game, [110, -130]);
    incomplete.odds?.outcomes.pop();
    expect(pregameMarketCompetitiveness(incomplete)).toBeNull();
    expect(pregameWatchabilityScore(incomplete)).toBe(60);

    const staleUpdate = new Date(
      Date.parse(game.scheduled_start_time) - 25 * 60 * 60 * 1000,
    ).toISOString();
    const stale = withOdds(game, [110, -130], staleUpdate);
    const malformed = withOdds(game, [110, -130], "not-a-date");
    expect(pregameMarketCompetitiveness(stale)).toBeNull();
    expect(pregameWatchabilityScore(stale)).toBe(60);
    expect(pregameMarketCompetitiveness(malformed)).toBeNull();
    expect(pregameWatchabilityScore(malformed)).toBe(60);

    const incompleteSoccer = withOdds(makeGame({ competition: "PREMIER_LEAGUE" }), [110, -130]);
    expect(pregameMarketCompetitiveness(incompleteSoccer)).toBeNull();
  });

  it("rejects invalid American odds", () => {
    expect(americanOddsImpliedProbability(0)).toBeNull();
    expect(americanOddsImpliedProbability(99)).toBeNull();
    expect(americanOddsImpliedProbability(-99)).toBeNull();
    expect(americanOddsImpliedProbability(Number.NaN)).toBeNull();
    expect(marketCompetitivenessFactor([0, -110])).toBeNull();
    expect(pregameWatchabilityScore(withOdds(makeGame({ competition: "NBA" }), [0, -110]))).toBe(
      60,
    );
  });
});

describe("thresholded scheduled watchability", () => {
  function scheduledGame(id: number, strength: number): Game {
    return makeGame({
      id,
      competition: "NBA",
      home_team_strength: recordStrength(strength),
      away_team_strength: recordStrength(strength),
    });
  }

  it("does not reward or penalize qualifying odds compared with missing odds", () => {
    const withoutOdds = scheduledGame(401, 0.7);
    const balancedOdds = withOdds(scheduledGame(402, 0.7), [-110, -110]);
    expect(pregameWatchabilityScore(withoutOdds)).toBe(76);
    expect(pregameWatchabilityScore(balancedOdds)).toBe(76);
    expect(sortGames([balancedOdds, withoutOdds], "watchability")[0].id).toBe(401);
  });

  it("puts markets below the 20 percent threshold in the low score band", () => {
    const atThreshold = withOdds(scheduledGame(403, 0.7), [-400, 400]);
    const belowThreshold = withOdds(scheduledGame(404, 1), [-425, 400]);
    expect(pregameFavoriteNonWinProbability(atThreshold)).toBeCloseTo(0.2);
    expect(pregameWatchabilityScore(atThreshold)).toBe(76);
    expect(pregameFavoriteNonWinProbability(belowThreshold)).toBeLessThan(0.2);
    expect(pregameWatchabilityScore(belowThreshold)).toBeLessThan(20);
    expect(sortGames([belowThreshold, atThreshold], "watchability")[0].id).toBe(403);
  });

  it("moves an elite mismatch below an acceptable matchup", () => {
    const eliteMismatch = withOdds(
      makeGame({
        id: 405,
        competition: "NBA",
        home_team_strength: recordStrength(1),
        away_team_strength: recordStrength(0.2),
      }),
      [-1200, 750],
    );
    const strongBalanced = withOdds(scheduledGame(406, 0.6), [-110, -110]);
    expect(pregameWatchabilityScore(eliteMismatch)).toBeLessThan(20);
    expect(sortGames([eliteMismatch, strongBalanced], "watchability")[0].id).toBe(406);
  });

  it("uses combined team strength after the market clears the threshold", () => {
    const elitePair = withOdds(
      makeGame({
        id: 407,
        competition: "NBA",
        home_team_strength: recordStrength(1),
        away_team_strength: recordStrength(0.7),
      }),
      [-350, 285],
    );
    const balancedPair = withOdds(scheduledGame(408, 0.7), [-110, -110]);
    expect(pregameFavoriteNonWinProbability(elitePair)).toBeGreaterThan(0.2);
    expect(pregameWatchabilityScore(elitePair)).toBe(88);
    expect(sortGames([balancedPair, elitePair], "watchability")[0].id).toBe(407);
  });

  it("uses market competitiveness only to break equal qualifying scores", () => {
    const skewed = withOdds(scheduledGame(409, 0.8), [-250, 205]);
    const balanced = withOdds(scheduledGame(410, 0.8), [-110, -110]);
    expect(pregameWatchabilityScore(skewed)).toBe(84);
    expect(pregameWatchabilityScore(balanced)).toBe(84);
    expect(sortGames([skewed, balanced], "watchability")[0].id).toBe(410);
  });

  it("includes draws in the soccer threshold and still rejects true mismatches", () => {
    const drawSupportedMatch = withOdds(
      makeGame({
        id: 411,
        competition: "PREMIER_LEAGUE",
        home_team_strength: recordStrength(1),
        away_team_strength: recordStrength(0.8),
      }),
      [-400, 500, 900],
    );
    const averageMatch = withOdds(
      makeGame({
        id: 412,
        competition: "PREMIER_LEAGUE",
        home_team_strength: recordStrength(0.5),
        away_team_strength: recordStrength(0.5),
      }),
      [200, 200, 200],
    );
    const trueMismatch = withOdds(
      makeGame({
        id: 413,
        competition: "PREMIER_LEAGUE",
        home_team_strength: recordStrength(1),
        away_team_strength: recordStrength(0.8),
      }),
      [-1000, 700, 1600],
    );
    expect(pregameFavoriteNonWinProbability(drawSupportedMatch)).toBeCloseTo(0.25);
    expect(sortGames([drawSupportedMatch, averageMatch], "watchability")[0].id).toBe(411);
    expect(pregameFavoriteNonWinProbability(trueMismatch)).toBeLessThan(0.2);
    expect(pregameWatchabilityScore(trueMismatch)).toBeLessThan(20);
    expect(sortGames([trueMismatch, averageMatch], "watchability")[0].id).toBe(412);
  });

  it("preserves relative ordering when every scheduled game lacks odds", () => {
    const weak = scheduledGame(414, 0.3);
    const average = scheduledGame(415, 0.5);
    const strong = scheduledGame(416, 0.8);
    expect(sortGames([average, weak, strong], "watchability").map(({ id }) => id)).toEqual([
      416, 415, 414,
    ]);
  });

  it("does not use pregame odds for live scoring or ordering", () => {
    const closeLate = makeGame({
      id: 417,
      competition: "NBA",
      status: "in_progress",
      period: 4,
      clock: "1:00",
      home_score: 100,
      away_score: 98,
    });
    const tiedEarly = makeGame({
      id: 418,
      competition: "NBA",
      status: "in_progress",
      period: 1,
      clock: "12:00",
      home_score: 0,
      away_score: 0,
    });
    const pricedCloseLate = withOdds(closeLate, [-1000, 650]);
    const pricedTiedEarly = withOdds(tiedEarly, [-110, -110]);
    expect(liveWatchabilityScore(pricedCloseLate)).toBe(liveWatchabilityScore(closeLate));
    expect(
      sortGames([pricedTiedEarly, pricedCloseLate], "watchability").map(({ id }) => id),
    ).toEqual([417, 418]);
  });
});

describe("basketball live calculations", () => {
  it("uses league quarter lengths, decimal clocks, and overtime clocks", () => {
    const cases: Array<[Partial<Game>, number]> = [
      [{ competition: "NBA", status: "in_progress", period: 1, clock: "12:00" }, 2880],
      [{ competition: "NBA", status: "in_progress", period: 2, clock: "0:00" }, 1440],
      [{ competition: "WNBA", status: "live", period: 4, clock: "12.3" }, 12.3],
      [{ competition: "WNBA", status: "live", period: 4, clock: "0.0" }, 0],
      [{ competition: "NBA", status: "in_progress", period: 5, clock: null }, 0],
    ];
    cases.forEach(([overrides, expected]) => {
      expect(basketballRegulationSecondsRemaining(makeGame(overrides))).toBe(expected);
    });
    expect(
      basketballGameSecondsRemaining(
        makeGame({ competition: "NBA", status: "in_progress", period: 5, clock: "5:00" }),
      ),
    ).toBe(300);
  });

  it("rejects malformed, impossible, and non-live clocks", () => {
    const cases: Partial<Game>[] = [
      { competition: "NBA", status: "in_progress", period: 2, clock: "12 minutes" },
      { competition: "WNBA", status: "in_progress", period: 2, clock: "11:00" },
      { competition: "NBA", status: "scheduled", period: 2, clock: "4:00" },
    ];
    cases.forEach((overrides) => {
      expect(basketballRegulationSecondsRemaining(makeGame(overrides))).toBeNull();
    });
  });

  it("uses calibrated basketball margin bands", () => {
    const cases: Array<[Partial<Game>, number]> = [
      [
        {
          competition: "NBA",
          status: "in_progress",
          period: 1,
          clock: "12:00",
          home_score: 0,
          away_score: 0,
        },
        40,
      ],
      [
        {
          competition: "NBA",
          status: "in_progress",
          period: 4,
          clock: "2:00",
          home_score: 98,
          away_score: 95,
        },
        93,
      ],
      [
        {
          competition: "WNBA",
          status: "in_progress",
          period: 4,
          clock: "0.0",
          home_score: 88,
          away_score: 67,
        },
        0,
      ],
    ];
    cases.forEach(([overrides, expected]) => {
      expect(basketballWatchabilityScore(makeGame(overrides))).toBe(expected);
    });
  });
});

describe("basketball watchability calibration", () => {
  const eliteStrength = { wins: 10, losses: 0, ties: null, rank: null };
  const neutralStrength = { wins: null, losses: null, ties: null, rank: null };

  function liveGame(
    id: number,
    period: number,
    clock: string,
    margin: number,
    elite = false,
  ): Game {
    return makeGame({
      id,
      external_game_id: `basketball-live-${id}`,
      competition: "NBA",
      scheduled_start_time: "2026-06-12T20:00:00Z",
      status: "in_progress",
      period,
      clock,
      home_score: margin,
      away_score: 0,
      home_team_strength: elite ? eliteStrength : neutralStrength,
      away_team_strength: elite ? eliteStrength : neutralStrength,
    });
  }

  function scheduledGame(id: number, homeRate: number, awayRate: number): Game {
    return makeGame({
      id,
      external_game_id: `basketball-pregame-${id}`,
      competition: "NBA",
      home_team_strength: recordStrength(homeRate),
      away_team_strength: recordStrength(awayRate),
    });
  }

  it("matches the calibrated live choices", () => {
    const choices: Array<[Game, Game, number]> = [
      [liveGame(201, 2, "0:00", 0), liveGame(202, 4, "2:00", 8), 202],
      [liveGame(203, 3, "8:00", 3), liveGame(204, 4, "2:00", 10), 204],
      [liveGame(205, 2, "0:00", 0, true), liveGame(206, 4, "1:00", 6), 206],
      [liveGame(207, 4, "12:00", 0), liveGame(208, 4, "3:00", 15, true), 208],
      [liveGame(209, 4, "0:30", 3), liveGame(210, 5, "5:00", 0), 209],
    ];
    choices.forEach(([a, b, expectedId]) => {
      expect(sortGames([a, b], "watchability")[0].id).toBe(expectedId);
    });
  });

  it("prefers balanced strength for scheduled games", () => {
    const twoStrongTeams = scheduledGame(211, 0.8, 0.8);
    const superstarMismatch = scheduledGame(212, 0.95, 0.6);
    expect(sortGames([superstarMismatch, twoStrongTeams], "watchability")[0].id).toBe(211);

    const twoBalancedTeams = scheduledGame(213, 0.65, 0.65);
    const sameAverageMismatch = scheduledGame(214, 0.8, 0.5);
    expect(sortGames([sameAverageMismatch, twoBalancedTeams], "watchability")[0].id).toBe(213);
  });
});

describe("soccer live calculations", () => {
  it("parses halves, stoppage time, halftime, extra time, and penalties", () => {
    const soccerGame = (period: number, clock: string | null) =>
      makeGame({ competition: "MLS", status: "in_progress", period, clock });
    const cases: Array<[Game, number | null]> = [
      [soccerGame(2, "68'"), 22],
      [soccerGame(1, "45'+2'"), 43],
      [soccerGame(2, "90'+5'"), 0],
      [soccerGame(2, "HT"), 45],
      [soccerGame(3, "105'"), 15],
      [soccerGame(5, null), 0],
      [soccerGame(2, "late"), null],
    ];
    cases.forEach(([game, expected]) => {
      expect(soccerRegulationMinutesRemaining(game)).toBe(expected);
    });
  });

  it("uses calibrated goal-margin bands and penalty urgency", () => {
    const score = (margin: number, clock = "90'") =>
      soccerWatchabilityScore(
        makeGame({
          competition: "PREMIER_LEAGUE",
          status: "in_progress",
          period: 2,
          clock,
          home_score: margin,
          away_score: 0,
        }),
      );
    expect(score(0, "0'")).toBe(55);
    expect(score(1, "88'")).toBe(89);
    expect(score(2)).toBe(50);
    expect(score(3)).toBe(25);
    expect(score(4)).toBe(0);
    expect(
      soccerWatchabilityScore(
        makeGame({
          competition: "WORLD_CUP",
          status: "in_progress",
          period: 5,
          home_score: 4,
          away_score: 1,
        }),
      ),
    ).toBe(100);
  });
});

describe("soccer watchability calibration", () => {
  const neutralStrength = { wins: null, losses: null, ties: null, rank: null };
  const eliteStrength = { wins: 10, losses: 0, ties: 0, rank: null };
  const strongStrength = { wins: 8, losses: 2, ties: 0, rank: null };

  function liveGame(
    id: number,
    period: number,
    clock: string | null,
    margin: number,
    strength: Game["home_team_strength"] = neutralStrength,
  ): Game {
    return makeGame({
      id,
      external_game_id: `soccer-live-${id}`,
      competition: "PREMIER_LEAGUE",
      scheduled_start_time: "2026-08-30T17:00:00Z",
      status: "in_progress",
      period,
      clock,
      home_score: margin,
      away_score: 0,
      home_team_strength: strength,
      away_team_strength: strength,
    });
  }

  function scheduledGame(id: number, homeRate: number, awayRate: number): Game {
    return makeGame({
      id,
      external_game_id: `soccer-pregame-${id}`,
      competition: "PREMIER_LEAGUE",
      home_team_strength: { ...recordStrength(homeRate), ties: 0 },
      away_team_strength: { ...recordStrength(awayRate), ties: 0 },
    });
  }

  it("matches the calibrated live choices", () => {
    const choices: Array<[Game, Game, number]> = [
      [liveGame(301, 2, "55'", 0), liveGame(302, 2, "82'", 1, eliteStrength), 302],
      [liveGame(303, 1, "25'", 0), liveGame(304, 2, "85'", 2, eliteStrength), 303],
      [liveGame(305, 2, "60'", 1), liveGame(306, 2, "88'", 2), 305],
      [liveGame(307, 2, "90'+3'", 0), liveGame(308, 4, "105'", 0), 308],
      [liveGame(309, 2, "88'", 1, strongStrength), liveGame(310, 5, null, 0), 310],
    ];
    choices.forEach(([a, b, expectedId]) => {
      expect(sortGames([a, b], "watchability")[0].id).toBe(expectedId);
    });
  });

  it("uses the shared balanced-strength rule for scheduled games", () => {
    const twoEliteTeams = scheduledGame(311, 0.8, 0.8);
    const eliteMismatch = scheduledGame(312, 0.95, 0.65);
    expect(sortGames([eliteMismatch, twoEliteTeams], "watchability")[0].id).toBe(311);

    const twoBalancedTeams = scheduledGame(313, 0.65, 0.65);
    const averageMismatch = scheduledGame(314, 0.8, 0.5);
    expect(sortGames([averageMismatch, twoBalancedTeams], "watchability")[0].id).toBe(313);
  });
});

describe("unified live watchability", () => {
  it("adds at most 15 points above neutral quality without penalizing weak teams", () => {
    const liveGame = {
      competition: "NBA" as const,
      status: "in_progress",
      period: 1,
      clock: "12:00",
      home_score: 0,
      away_score: 0,
    };
    const neutral = makeGame(liveGame);
    const elite = makeGame({
      ...liveGame,
      home_team_strength: { wins: 10, losses: 0, ties: null, rank: null },
      away_team_strength: { wins: 10, losses: 0, ties: null, rank: null },
    });
    const weak = makeGame({
      ...liveGame,
      home_team_strength: { wins: 2, losses: 8, ties: null, rank: null },
      away_team_strength: { wins: 2, losses: 8, ties: null, rank: null },
    });
    expect(liveWatchabilityScore(neutral)).toBe(40);
    expect(liveWatchabilityScore(elite)).toBe(55);
    expect(liveWatchabilityScore(weak)).toBe(40);
    expect(liveWatchabilityScore({ ...elite, period: 5, clock: "5:00" })).toBe(100);
  });
});

function recordStrength(rate: number): Game["home_team_strength"] {
  return {
    wins: rate * 100,
    losses: (1 - rate) * 100,
    ties: null,
    rank: null,
  };
}
