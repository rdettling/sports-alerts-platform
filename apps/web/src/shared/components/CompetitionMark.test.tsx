import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompetitionMark } from "./CompetitionMark";

describe("CompetitionMark", () => {
  it.each([
    ["NBA", "NBA", "https://cdn.nba.com/logos/leagues/logo-nba-logoman.svg"],
    ["WNBA", "WNBA", "https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png"],
    ["NFL", "NFL", "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png"],
    ["MLB", "MLB", "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"],
    [
      "MLS",
      "MLS",
      "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg",
    ],
    ["LA_LIGA", "LALIGA", "https://a.espncdn.com/i/leaguelogos/soccer/500/15.png"],
    ["PREMIER_LEAGUE", "EPL", "https://a.espncdn.com/i/leaguelogos/soccer/500/23.png"],
  ])("renders the configured %s artwork", (competition, badge, logoUrl) => {
    render(<CompetitionMark competition={competition} />);

    expect(screen.getByRole("img", { name: `${badge} logo` })).toHaveAttribute("src", logoUrl);
  });

  it("renders the ESPN college football artwork without text", () => {
    render(<CompetitionMark competition="FBS" />);

    const mark = screen.getByRole("img", { name: "FBS logo" });
    expect(mark).toHaveAttribute(
      "src",
      "https://a.espncdn.com/redesign/assets/img/icons/ESPN-icon-football-college.png",
    );
    expect(mark).not.toHaveTextContent("FBS");
  });

  it("renders the bundled World Cup artwork", () => {
    render(<CompetitionMark competition="WORLD_CUP" />);

    expect(screen.getByRole("img", { name: "WC logo" }).getAttribute("src")).toContain(
      "world-cup-mark",
    );
  });

  it("falls back to the league badge when artwork fails", () => {
    render(<CompetitionMark competition="PREMIER_LEAGUE" />);

    fireEvent.error(screen.getByRole("img", { name: "EPL logo" }));

    expect(screen.getByText("EPL")).toBeInTheDocument();
  });

  it("uses the competition code when no artwork is configured", () => {
    render(<CompetitionMark competition="new_league" />);

    expect(screen.getByText("NEW_LEAGUE")).toBeInTheDocument();
  });
});
