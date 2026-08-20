import { apiRequest } from "../client";
import type { Game } from "../types";

type ListGamesOptions = {
  competition?: string;
  includeFinals?: boolean;
  limit?: number;
};

export function listGames(options: ListGamesOptions = {}): Promise<Game[]> {
  const params = new URLSearchParams();
  if (options.competition) params.set("competition", options.competition);
  if (options.includeFinals !== undefined)
    params.set("include_finals", String(options.includeFinals));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const query = params.toString();
  return apiRequest<Game[]>(query ? `/games?${query}` : "/games");
}
