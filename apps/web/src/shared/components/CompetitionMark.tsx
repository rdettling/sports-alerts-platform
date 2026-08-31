import { useState } from "react";

import worldCupMark from "../../assets/world-cup-mark.png";
import { type Competition } from "../api";

const COMPETITION_MARKS = {
  NBA: {
    logoUrl: "https://cdn.nba.com/logos/leagues/logo-nba-logoman.svg",
    fallback: "NBA",
  },
  WNBA: {
    logoUrl: "https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png",
    fallback: "WNBA",
  },
  NFL: {
    logoUrl: "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png",
    fallback: "NFL",
  },
  FBS: {
    logoUrl: "https://a.espncdn.com/redesign/assets/img/icons/ESPN-icon-football-college.png",
    fallback: "FBS",
  },
  MLB: {
    logoUrl: "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg",
    fallback: "MLB",
  },
  MLS: {
    logoUrl: "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg",
    fallback: "MLS",
  },
  LA_LIGA: {
    logoUrl: "https://a.espncdn.com/i/leaguelogos/soccer/500/15.png",
    fallback: "LALIGA",
  },
  PREMIER_LEAGUE: {
    logoUrl: "https://a.espncdn.com/i/leaguelogos/soccer/500/23.png",
    fallback: "EPL",
  },
  WORLD_CUP: {
    logoUrl: worldCupMark,
    fallback: "WC",
  },
} satisfies Record<Competition, { logoUrl: string; fallback: string }>;

export function CompetitionMark({
  competition,
  className = "",
  decorative = false,
}: {
  competition: string;
  className?: string;
  decorative?: boolean;
}) {
  const normalized = competition.toUpperCase();
  const presentation = COMPETITION_MARKS[normalized as Competition];
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const logoUrl = presentation?.logoUrl;
  const modifier = normalized.toLowerCase().replace(/[^a-z0-9_-]/g, "-");
  const fallback = presentation?.fallback ?? normalized;

  return (
    <span
      className={`competition-mark ${className}`.trim()}
      aria-hidden={decorative ? true : undefined}
    >
      {logoUrl && failedUrl !== logoUrl ? (
        <img
          src={logoUrl}
          alt={decorative ? "" : `${fallback} logo`}
          className={`competition-mark-image competition-${modifier}`}
          onError={() => setFailedUrl(logoUrl)}
        />
      ) : (
        <span className="competition-mark-fallback">{fallback}</span>
      )}
    </span>
  );
}
