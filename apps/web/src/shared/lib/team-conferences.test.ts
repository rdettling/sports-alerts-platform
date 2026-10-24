import { expect, it } from "vitest";

import { type Competition, type Team } from "../api";
import { gameConferenceOptions, teamConferenceOptions } from "./team-conferences";

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
