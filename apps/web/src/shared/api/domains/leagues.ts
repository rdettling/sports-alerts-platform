import { apiRequest } from "../client";
import type { LeagueSetting } from "../types";

export function listLeagues(): Promise<LeagueSetting[]> {
  return apiRequest<LeagueSetting[]>("/leagues");
}
