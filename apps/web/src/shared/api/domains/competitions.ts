import { apiRequest } from "../client";
import type { CompetitionSetting } from "../types";

export function listCompetitions(): Promise<CompetitionSetting[]> {
  return apiRequest<CompetitionSetting[]>("/competitions");
}
