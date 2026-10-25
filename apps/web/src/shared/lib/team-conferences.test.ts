import { expect, it } from "vitest";

import { type Competition, type Game, type Team } from "../api";
import {
  gameConferenceOptions,
  matchesGameConference,
  teamConferenceOptions,
} from "./team-conferences";

it("keeps conference options scoped to the selected competition", () => {
  const teams: Team[] = [
    {
      id: 1,
      sport: "football",
      external_team_id: "1",
      name: "One",
      abbreviation: "ONE",
      competitions: ["FBS"],
      conference: "SEC",
    },
    {
      id: 2,
      sport: "basketball",
      external_team_id: "1",
      name: "Two",
      abbreviation: "TWO",
      competitions: ["NBA"],
      conference: "Other",
    },
    {
      id: 3,
      sport: "football",
      external_team_id: "2",
      name: "Three",
      abbreviation: "THR",
      competitions: ["FBS"],
      conference: "Big Ten",
    },
    {
      id: 4,
      sport: "football",
      external_team_id: "3",
      name: "Four",
      abbreviation: "FOUR",
      competitions: ["FBS"],
      conference: "SEC",
    },
  ];
  expect(teamConferenceOptions(teams, "FBS")).toEqual(["Big Ten", "SEC"]);
  expect(teamConferenceOptions(teams, "NBA")).toEqual(["Other"]);
  expect(teamConferenceOptions(teams, "all")).toEqual([]);
});

it.each<Competition>(["FBS", "NCAAB"])(
  "keeps the %s preset filters available without scheduled games",
  (competition) => {
    expect(gameConferenceOptions([], competition)).toEqual(["Top 25", "Power Conferences"]);
  },
);

it.each<Competition>(["FBS", "NCAAB"])(
  "matches either power-conference participant in %s and excludes Pac-12-only games",
  (competition) => {
    const matchup = (homeConference: string | null, awayConference: string | null) =>
      ({
        competition,
        home_team: { conference: homeConference },
        away_team: { conference: awayConference },
      }) as Game;
    for (const conference of ["ACC", "Big 12", "Big Ten", "SEC"]) {
      expect(matchesGameConference(matchup(conference, "American"), "Power Conferences")).toBe(
        true,
      );
      expect(matchesGameConference(matchup("American", conference), "Power Conferences")).toBe(
        true,
      );
    }
    expect(matchesGameConference(matchup("Pac-12", "Pac-12"), "Power Conferences")).toBe(false);
    expect(matchesGameConference(matchup("Pac-12", "Mountain West"), "Power Conferences")).toBe(
      false,
    );
    expect(matchesGameConference(matchup("Sun Belt", "American"), "Power Conferences")).toBe(false);
    expect(matchesGameConference(matchup(null, null), "Power Conferences")).toBe(false);
    expect(matchesGameConference(matchup("Big East", "West Coast"), "Power Conferences")).toBe(
      competition === "NCAAB",
    );
    expect(matchesGameConference(matchup("Pac-12", "Mountain West"), "Pac-12")).toBe(true);
    expect(matchesGameConference(matchup("Pac-12", "Mountain West"), "all")).toBe(true);
  },
);
