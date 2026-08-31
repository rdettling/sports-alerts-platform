import { describe, expect, it } from "vitest";

import type { Game } from "../../../../shared/api";
import { filterGamesByDay, resolveSelectedDay, sortGames } from "./games-view-utils";

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

describe("resolveSelectedDay", () => {
  const days = [
    { key: "2026-09-05", label: "Sat, Sep 5", count: 2 },
    { key: "2026-09-07", label: "Mon, Sep 7", count: 1 },
  ];

  it("selects today, the next upcoming day, or the latest past day", () => {
    expect(resolveSelectedDay(days, null, "2026-09-05")).toBe("2026-09-05");
    expect(resolveSelectedDay(days, null, "2026-09-04")).toBe("2026-09-05");
    expect(resolveSelectedDay(days, null, "2026-09-08")).toBe("2026-09-07");
  });

  it("keeps a valid selection and chooses the later closest day on a tie", () => {
    expect(resolveSelectedDay(days, "2026-09-05", "2026-09-01")).toBe("2026-09-05");
    expect(resolveSelectedDay(days, "2026-09-06", "2026-09-01")).toBe("2026-09-07");
    expect(resolveSelectedDay([], "2026-09-06", "2026-09-01")).toBeNull();
  });
});

describe("sortGames", () => {
  function footballGame(id: number, overrides: Partial<Game>): Game {
    return makeGame({
      id,
      external_game_id: `football-${id}`,
      competition: "NFL",
      scheduled_start_time: `2026-09-06T${String(10 + id).padStart(2, "0")}:00:00Z`,
      ...overrides,
    });
  }

  const closeLate = footballGame(1, {
    status: "in_progress",
    period: 4,
    clock: "02:00",
    home_score: 24,
    away_score: 21,
  });
  const tiedEarly = footballGame(2, {
    status: "in_progress",
    period: 1,
    clock: "15:00",
    home_score: 0,
    away_score: 0,
  });
  const lateBlowout = footballGame(3, {
    status: "in_progress",
    period: 4,
    clock: "01:00",
    home_score: 35,
    away_score: 7,
  });
  const scheduled = footballGame(4, { status: "scheduled" });
  const final = footballGame(5, { status: "final", is_final: true });
  const postponed = footballGame(6, { status: "postponed" });

  it("sorts live games by watchability before non-live status groups", () => {
    expect(
      sortGames([postponed, final, scheduled, lateBlowout, tiedEarly, closeLate], "live_first").map(
        ({ id }) => id,
      ),
    ).toEqual([1, 2, 3, 4, 5, 6]);
    expect(
      sortGames(
        [postponed, final, scheduled, lateBlowout, tiedEarly, closeLate],
        "watchability",
      ).map(({ id }) => id),
    ).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("sorts live games by least time remaining while preserving non-live games", () => {
    expect(
      sortGames(
        [postponed, final, scheduled, closeLate, tiedEarly, lateBlowout],
        "ending_soon",
      ).map(({ id }) => id),
    ).toEqual([3, 1, 2, 4, 5, 6]);
  });

  it("puts uncalculable live games last within live and reverses final kickoff order", () => {
    const invalidLive = footballGame(7, {
      status: "in_progress",
      period: 4,
      clock: null,
      home_score: 10,
      away_score: 10,
    });
    const laterFinal = footballGame(8, {
      status: "final",
      is_final: true,
      scheduled_start_time: "2026-09-06T20:00:00Z",
    });
    expect(
      sortGames([final, invalidLive, laterFinal, closeLate], "watchability").map(({ id }) => id),
    ).toEqual([1, 7, 8, 5]);
  });

  it("uses kickoff and game ID as deterministic live tie-breakers", () => {
    const sameA = footballGame(10, {
      status: "in_progress",
      period: 4,
      clock: "03:00",
      home_score: 20,
      away_score: 17,
      scheduled_start_time: "2026-09-06T17:00:00Z",
    });
    const sameB = footballGame(9, {
      status: "in_progress",
      period: 4,
      clock: "03:00",
      home_score: 27,
      away_score: 24,
      scheduled_start_time: "2026-09-06T17:00:00Z",
    });
    expect(sortGames([sameA, sameB], "watchability").map(({ id }) => id)).toEqual([9, 10]);
  });

  it("returns no games when no date is selected", () => {
    expect(filterGamesByDay([scheduled], null)).toEqual([]);
  });

  it("sorts baseball by inning progress or watchability", () => {
    const close = makeGame({
      id: 20,
      status: "in_progress",
      period: 8,
      clock: "Bottom 8th",
      home_score: 4,
      away_score: 3,
    });
    const early = makeGame({
      id: 21,
      status: "in_progress",
      period: 3,
      clock: "Top 3rd",
      home_score: 1,
      away_score: 1,
    });
    const blowout = makeGame({
      id: 22,
      status: "in_progress",
      period: 9,
      clock: "Bottom 9th",
      home_score: 8,
      away_score: 2,
    });
    expect(sortGames([blowout, early, close], "watchability").map(({ id }) => id)).toEqual([
      20, 21, 22,
    ]);
    expect(sortGames([close, early, blowout], "ending_soon").map(({ id }) => id)).toEqual([
      22, 20, 21,
    ]);
  });

  it("sorts basketball by regulation time or watchability", () => {
    const close = makeGame({
      id: 30,
      competition: "NBA",
      status: "in_progress",
      period: 4,
      clock: "1:00",
      home_score: 105,
      away_score: 103,
    });
    const early = makeGame({
      id: 31,
      competition: "NBA",
      status: "in_progress",
      period: 1,
      clock: "12:00",
      home_score: 0,
      away_score: 0,
    });
    const blowout = makeGame({
      id: 32,
      competition: "NBA",
      status: "in_progress",
      period: 4,
      clock: "0.0",
      home_score: 120,
      away_score: 90,
    });
    expect(sortGames([blowout, early, close], "watchability").map(({ id }) => id)).toEqual([
      30, 31, 32,
    ]);
    expect(sortGames([close, early, blowout], "ending_soon").map(({ id }) => id)).toEqual([
      32, 30, 31,
    ]);
  });

  it("sorts soccer by time remaining or watchability", () => {
    const close = makeGame({
      id: 40,
      competition: "MLS",
      status: "in_progress",
      period: 2,
      clock: "86'",
      home_score: 2,
      away_score: 1,
    });
    const early = makeGame({
      id: 41,
      competition: "MLS",
      status: "in_progress",
      period: 1,
      clock: "10'",
      home_score: 0,
      away_score: 0,
    });
    const blowout = makeGame({
      id: 42,
      competition: "MLS",
      status: "in_progress",
      period: 2,
      clock: "90'+4'",
      home_score: 4,
      away_score: 0,
    });
    expect(sortGames([blowout, early, close], "watchability").map(({ id }) => id)).toEqual([
      40, 41, 42,
    ]);
    expect(sortGames([close, early, blowout], "ending_soon").map(({ id }) => id)).toEqual([
      42, 40, 41,
    ]);
  });

  it("uses team quality for scheduled watchability without moving it above live", () => {
    const liveBlowout = makeGame({
      id: 50,
      competition: "WNBA",
      status: "in_progress",
      period: 4,
      clock: "0.0",
      home_score: 100,
      away_score: 70,
    });
    const weakerEarlier = makeGame({
      id: 51,
      competition: "WNBA",
      scheduled_start_time: "2026-05-28T18:00:00Z",
      home_team_strength: { wins: 2, losses: 8, ties: null, rank: null },
      away_team_strength: { wins: 3, losses: 7, ties: null, rank: null },
    });
    const strongerLater = makeGame({
      id: 52,
      competition: "WNBA",
      scheduled_start_time: "2026-05-28T20:00:00Z",
      home_team_strength: { wins: 9, losses: 1, ties: null, rank: null },
      away_team_strength: { wins: 8, losses: 2, ties: null, rank: null },
    });
    expect(
      sortGames([weakerEarlier, strongerLater, liveBlowout], "watchability").map(({ id }) => id),
    ).toEqual([50, 52, 51]);
    expect(
      sortGames([strongerLater, liveBlowout, weakerEarlier], "live_first").map(({ id }) => id),
    ).toEqual([50, 51, 52]);
    expect(
      sortGames([strongerLater, liveBlowout, weakerEarlier], "ending_soon").map(({ id }) => id),
    ).toEqual([50, 51, 52]);
  });

  it("uses status-aware watchability for mixed competitions", () => {
    const laterLiveFootball = footballGame(60, {
      scheduled_start_time: "2026-09-06T20:00:00Z",
      status: "in_progress",
      period: 4,
      clock: "00:30",
      home_score: 20,
      away_score: 20,
    });
    const earlierScheduledBaseball = makeGame({
      id: 61,
      scheduled_start_time: "2026-09-06T17:00:00Z",
    });
    expect(
      sortGames([laterLiveFootball, earlierScheduledBaseball], "watchability").map(({ id }) => id),
    ).toEqual([60, 61]);
    expect(
      sortGames([laterLiveFootball, earlierScheduledBaseball], "start_time").map(({ id }) => id),
    ).toEqual([61, 60]);
  });

  it("compares normalized remaining game shares across sports", () => {
    const lateFootball = footballGame(62, {
      status: "in_progress",
      period: 4,
      clock: "02:00",
    });
    const lateBaseball = makeGame({
      id: 63,
      status: "in_progress",
      period: 8,
      clock: "Bottom 8th",
      home_score: 4,
      away_score: 3,
    });
    expect(sortGames([lateBaseball, lateFootball], "ending_soon").map(({ id }) => id)).toEqual([
      62, 63,
    ]);
  });
});
