import { apiRequest } from "../client";
import type { CurrentFollows } from "../types";

export function listFollows(token: string): Promise<CurrentFollows> {
  return apiRequest<CurrentFollows>("/follows", { token });
}

export function followTeam(token: string, teamId: number): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/follows/teams/${teamId}`, { method: "POST", token });
}

export function followLeague(token: string, league: "NBA" | "MLB"): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/follows/leagues/${league}`, { method: "POST", token });
}

export function unfollowLeague(token: string, league: "NBA" | "MLB"): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/follows/leagues/${league}`, { method: "DELETE", token });
}

export function unfollowTeam(token: string, teamId: number): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/follows/teams/${teamId}`, { method: "DELETE", token });
}

export function followGame(token: string, gameId: number): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/follows/games/${gameId}`, { method: "POST", token });
}

export function unfollowGame(token: string, gameId: number): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/follows/games/${gameId}`, { method: "DELETE", token });
}
