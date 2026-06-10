import { apiRequest } from "../client";
import type { SportsUpdatesFeed } from "../types";

export function listUpdates(token: string, limit: number = 30): Promise<SportsUpdatesFeed> {
  return apiRequest<SportsUpdatesFeed>(`/updates?limit=${encodeURIComponent(String(limit))}`, { token });
}
