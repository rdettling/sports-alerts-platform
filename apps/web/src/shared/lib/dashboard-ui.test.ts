import { describe, expect, it } from "vitest";

import { competitionBadgeLabel, competitionLogoUrl } from "./dashboard-ui";

describe("dashboard utilities", () => {
  it("uses the MLS crest instead of a text fallback", () => {
    expect(competitionLogoUrl("MLS")).toBe(
      "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg",
    );
  });

  it("uses the WNBA competition mark", () => {
    expect(competitionLogoUrl("WNBA")).toBe(
      "https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png",
    );
  });

  it("uses the NFL competition mark", () => {
    expect(competitionLogoUrl("NFL")).toBe("https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png");
  });

  it("uses the La Liga competition mark", () => {
    expect(competitionLogoUrl("LA_LIGA")).toBe(
      "https://a.espncdn.com/i/leaguelogos/soccer/500/15.png",
    );
    expect(competitionBadgeLabel("LA_LIGA")).toBe("LALIGA");
  });

  it("uses the Premier League mark", () => {
    expect(competitionLogoUrl("PREMIER_LEAGUE")).toBe(
      "https://a.espncdn.com/i/leaguelogos/soccer/500/23.png",
    );
    expect(competitionBadgeLabel("PREMIER_LEAGUE")).toBe("EPL");
  });
});
