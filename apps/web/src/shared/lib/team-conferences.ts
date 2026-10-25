import { type Competition, type Game, type Team } from "../api";

export function teamConferenceOptions(teams: Team[], competition: "all" | Competition): string[] {
  return [
    ...new Set(
      teams
        .filter((team) => competition !== "all" && team.competitions.includes(competition))
        .map((team) => team.conference)
        .filter((conference): conference is string => typeof conference === "string"),
    ),
  ].sort((a, b) => a.localeCompare(b));
}

export const TOP_25_FILTER = "Top 25";
export const POWER_CONFERENCES_FILTER = "Power Conferences";

const COMMON_POWER_CONFERENCES = ["ACC", "Big 12", "Big Ten", "SEC"];
export const POWER_CONFERENCES: Partial<Record<Competition, string[]>> = {
  FBS: COMMON_POWER_CONFERENCES,
  NCAAB: [...COMMON_POWER_CONFERENCES, "Big East"].sort((a, b) => a.localeCompare(b)),
};

export function gameConferenceOptions(teams: Team[], competition: "all" | Competition): string[] {
  const conferences = teamConferenceOptions(teams, competition);
  return competition !== "all" && POWER_CONFERENCES[competition]
    ? [TOP_25_FILTER, POWER_CONFERENCES_FILTER, ...conferences]
    : conferences;
}

export function matchesGameConference(game: Game, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === TOP_25_FILTER) {
    return [game.home_team_strength.rank, game.away_team_strength.rank].some(
      (rank) => rank !== null && rank >= 1 && rank <= 25,
    );
  }
  const conferences = [game.home_team.conference, game.away_team.conference];
  if (filter === POWER_CONFERENCES_FILTER) {
    const powerConferences = POWER_CONFERENCES[game.competition] ?? [];
    return conferences.some(
      (conference) => conference !== null && powerConferences.includes(conference),
    );
  }
  return conferences.includes(filter);
}
