import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TeamLogo } from "./TeamLogo";

describe("TeamLogo", () => {
  it("uses the ESPN NHL logo path for hockey teams", () => {
    render(
      <TeamLogo
        team={{
          id: 1,
          sport: "hockey",
          external_team_id: "1",
          name: "Boston Bruins",
          abbreviation: "BOS",
          competitions: ["NHL"],
          conference: null,
        }}
      />,
    );

    expect(screen.getByRole("img", { name: "Boston Bruins logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/nhl/500/bos.png",
    );
  });
});
