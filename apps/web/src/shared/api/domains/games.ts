import { apiRequest } from "../client";
import type { Game } from "../types";

type ListGamesOptions = {
  league?: string;
  includeFinals?: boolean;
  limit?: number;
};

export function listGames(options: ListGamesOptions = {}): Promise<Game[]> {
  const params = new URLSearchParams();
  if (options.league) params.set("league", options.league);
  if (options.includeFinals !== undefined)
    params.set("include_finals", String(options.includeFinals));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const query = params.toString();
  return apiRequest<Game[]>(query ? `/games?${query}` : "/games");
}
