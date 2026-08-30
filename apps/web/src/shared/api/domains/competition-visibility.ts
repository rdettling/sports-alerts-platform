import { apiRequest } from "../client";
import type { Competition, CompetitionVisibility } from "../types";

export function getCompetitionVisibility(token: string): Promise<CompetitionVisibility> {
  return apiRequest<CompetitionVisibility>("/competition-visibility", { token });
}

export function updateCompetitionVisibility(
  token: string,
  hiddenCompetitions: Competition[],
): Promise<CompetitionVisibility> {
  return apiRequest<CompetitionVisibility>("/competition-visibility", {
    method: "PUT",
    token,
    body: JSON.stringify({ hidden_competitions: hiddenCompetitions }),
  });
}
