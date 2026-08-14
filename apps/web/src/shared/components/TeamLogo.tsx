import { useState } from "react";

import { type Team } from "../api";

function teamLogoUrl(team: Team): string {
  const abbreviation = team.abbreviation.toLowerCase();
  if (team.league === "MLS") {
    return `https://a.espncdn.com/i/teamlogos/soccer/500/${team.external_team_id}.png`;
  }
  if (team.league === "MLB") {
    return `https://a.espncdn.com/i/teamlogos/mlb/500/${abbreviation}.png`;
  }
  if (team.league === "NBA") {
    return `https://a.espncdn.com/i/teamlogos/nba/500/${abbreviation}.png`;
  }
  if (team.league === "WNBA") {
    return `https://a.espncdn.com/i/teamlogos/wnba/500/${abbreviation}.png`;
  }
  if (team.league === "WORLD_CUP") {
    return `https://a.espncdn.com/i/teamlogos/countries/500/${abbreviation}.png`;
  }
  return "";
}

export function TeamLogo({ team, size = 26 }: { team: Team; size?: number }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span className="team-logo-fallback" style={{ width: size, height: size }}>
        {team.abbreviation.slice(0, 2)}
      </span>
    );
  }

  return (
    <img
      className="team-logo"
      src={teamLogoUrl(team)}
      width={size}
      height={size}
      alt={`${team.name} logo`}
      onError={() => setFailed(true)}
    />
  );
}
