import { describe, expect, it } from "vitest";

import type { Game } from "../../../../shared/api";
import {
  baseballHalfInningsRemaining,
  baseballWatchabilityScore,
  basketballGameSecondsRemaining,
  basketballRegulationSecondsRemaining,
  basketballWatchabilityScore,
  footballRegulationSecondsRemaining,
  footballWatchabilityScore,
  liveWatchabilityScore,
  matchupQualityFactor,
  pregameMatchupPriority,
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
      expect(sortGames([a, b], "watchability", "NFL")[0].id).toBe(expectedId);
    });
  });

  it("prefers two strong scheduled teams and ignores kickoff proximity", () => {
    const firstVsTwentyFifth = rankedGame(109, 1, 25, "2026-09-06T17:00:00Z");
    const tenthVsEleventh = rankedGame(110, 10, 11, "2026-09-06T17:00:00Z");
    expect(sortGames([firstVsTwentyFifth, tenthVsEleventh], "watchability", "FBS")[0].id).toBe(110);

    const strongerLater = rankedGame(113, 2, 4, "2026-09-06T21:00:00Z");
    const weakerSooner = rankedGame(114, 15, 18, "2026-09-06T17:10:00Z");
    expect(sortGames([weakerSooner, strongerLater], "watchability", "FBS")[0].id).toBe(113);

    const identicalLater = rankedGame(115, 8, 9, "2026-09-06T21:00:00Z");
    const identicalSooner = rankedGame(116, 8, 9, "2026-09-06T17:10:00Z");
    expect(
      sortGames([identicalSooner, identicalLater], "watchability", "FBS").map(({ id }) => id),
    ).toEqual([115, 116]);
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
    expect(sortGames([undefeatedMismatch, twoNineAndOneTeams], "watchability", "NFL")[0].id).toBe(
      111,
    );
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

  it("combines average matchup strength with the weaker team", () => {
    const game = makeGame({
      competition: "NBA",
      home_team_strength: { wins: 8, losses: 2, ties: null, rank: null },
      away_team_strength: { wins: 6, losses: 4, ties: null, rank: null },
    });
    expect(matchupQualityFactor(game)).toBeCloseTo(0.685);
    expect(pregameMatchupPriority(game)).toBeCloseTo(68.5);

    const rankedFbsMatchup = makeGame({
      competition: "FBS",
      home_team_strength: { wins: 1, losses: 8, ties: 0, rank: 1 },
      away_team_strength: { wins: 10, losses: 0, ties: 0, rank: null },
    });
    expect(pregameMatchupPriority(rankedFbsMatchup)).toBeCloseTo(82.75);
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
      expect(sortGames([a, b], "watchability", "NBA")[0].id).toBe(expectedId);
    });
  });

  it("prefers balanced strength for scheduled games", () => {
    const twoStrongTeams = scheduledGame(211, 0.8, 0.8);
    const superstarMismatch = scheduledGame(212, 0.95, 0.6);
    expect(sortGames([superstarMismatch, twoStrongTeams], "watchability", "NBA")[0].id).toBe(211);

    const twoBalancedTeams = scheduledGame(213, 0.65, 0.65);
    const sameAverageMismatch = scheduledGame(214, 0.8, 0.5);
    expect(sortGames([sameAverageMismatch, twoBalancedTeams], "watchability", "NBA")[0].id).toBe(
      213,
    );
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
      expect(sortGames([a, b], "watchability", "PREMIER_LEAGUE")[0].id).toBe(expectedId);
    });
  });

  it("uses the shared balanced-strength rule for scheduled games", () => {
    const twoEliteTeams = scheduledGame(311, 0.8, 0.8);
    const eliteMismatch = scheduledGame(312, 0.95, 0.65);
    expect(sortGames([eliteMismatch, twoEliteTeams], "watchability", "PREMIER_LEAGUE")[0].id).toBe(
      311,
    );

    const twoBalancedTeams = scheduledGame(313, 0.65, 0.65);
    const averageMismatch = scheduledGame(314, 0.8, 0.5);
    expect(
      sortGames([averageMismatch, twoBalancedTeams], "watchability", "PREMIER_LEAGUE")[0].id,
    ).toBe(313);
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
