import worldCupMark from "../../assets/world-cup-mark.png";

export const PREFERENCE_LABELS: Record<string, string> = {
  game_start: "Game start",
  close_game_late: "Close game late",
  overtime_start: "Overtime start",
  inning_start: "Inning start",
  extra_innings_start: "Extra innings start",
  second_half_start: "Second half start",
  extra_time_start: "Extra time start",
  penalty_kicks: "Penalty kicks",
  score_changed: "Score change",
  final_result: "Final result",
};

export function messageFromUnknown(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}

export function competitionLogoUrl(competition: string | null | undefined): string | null {
  const normalized = (competition || "").toUpperCase();
  if (normalized === "NBA") return "https://cdn.nba.com/logos/leagues/logo-nba-logoman.svg";
  if (normalized === "WNBA") return "https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png";
  if (normalized === "NFL") return "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png";
  if (normalized === "MLB") return "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg";
  if (normalized === "MLS") {
    return "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg";
  }
  if (normalized === "LA_LIGA") {
    return "https://a.espncdn.com/i/leaguelogos/soccer/500/15.png";
  }
  if (normalized === "PREMIER_LEAGUE") {
    return "https://a.espncdn.com/i/leaguelogos/soccer/500/23.png";
  }
  if (normalized === "WORLD_CUP") return worldCupMark;
  return null;
}

export function competitionBadgeLabel(competition: string | null | undefined): string {
  const normalized = (competition || "").toUpperCase();
  if (normalized === "LA_LIGA") return "LALIGA";
  if (normalized === "PREMIER_LEAGUE") return "EPL";
  if (normalized === "WORLD_CUP") return "WC";
  return normalized || "N/A";
}
