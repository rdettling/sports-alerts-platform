import { apiRequest } from "../client";
import type { Game } from "../types";

export function listGames(): Promise<Game[]> {
  return apiRequest<Game[]>("/games");
}
