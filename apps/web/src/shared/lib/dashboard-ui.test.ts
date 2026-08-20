import { describe, expect, it } from "vitest";

import { leagueBadgeLabel, leagueLogoUrl } from "./dashboard-ui";

describe("dashboard utilities", () => {
  it("uses the MLS crest instead of a text fallback", () => {
    expect(leagueLogoUrl("MLS")).toBe(
      "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg",
    );
  });

  it("uses the WNBA league mark", () => {
    expect(leagueLogoUrl("WNBA")).toBe("https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png");
  });

  it("uses the NFL league mark", () => {
    expect(leagueLogoUrl("NFL")).toBe("https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png");
  });

  it("uses the La Liga league mark", () => {
    expect(leagueLogoUrl("LA_LIGA")).toBe("https://a.espncdn.com/i/leaguelogos/soccer/500/15.png");
    expect(leagueBadgeLabel("LA_LIGA")).toBe("LALIGA");
  });

  it("uses the Premier League mark", () => {
    expect(leagueLogoUrl("PREMIER_LEAGUE")).toBe(
      "https://a.espncdn.com/i/leaguelogos/soccer/500/23.png",
    );
    expect(leagueBadgeLabel("PREMIER_LEAGUE")).toBe("EPL");
  });
});
