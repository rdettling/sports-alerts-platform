import { apiRequest } from "../client";
import type { Team } from "../types";

export function listTeams(): Promise<Team[]> {
  return apiRequest<Team[]>("/teams");
}
