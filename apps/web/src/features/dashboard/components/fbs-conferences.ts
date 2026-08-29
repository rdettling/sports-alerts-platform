import { type Team } from "../../../shared/api";

export function fbsConferenceOptions(teams: Team[]): string[] {
  return [
    ...new Set(
      teams
        .filter((team) => team.competitions.includes("FBS"))
        .map((team) => team.conference)
        .filter((conference): conference is string => conference !== null),
    ),
  ].sort((a, b) => a.localeCompare(b));
}
