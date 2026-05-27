import { apiRequest } from "../client";
import type {
  AlertHistoryItem,
  AlertPreference,
  AlertPreferenceGroup,
  AlertType,
  DeliveryStatus,
  GameAlertPreferenceItem,
  GameAlertPreferences,
  League,
} from "../types";

export function listAlertPreferences(token: string): Promise<AlertPreferenceGroup[]> {
  return apiRequest<AlertPreferenceGroup[]>("/alert-preferences", { token });
}

export function updateAlertPreference(
  token: string,
  league: League,
  alertType: string,
  payload: {
    is_enabled?: boolean;
    close_game_margin_threshold?: number;
    close_game_time_threshold_seconds?: number;
    inning_start_threshold?: number;
  },
): Promise<AlertPreference> {
  return apiRequest<AlertPreference>(`/alert-preferences/leagues/${league}/${alertType}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

export function getGameAlertPreferences(token: string, gameId: number): Promise<GameAlertPreferences> {
  return apiRequest<GameAlertPreferences>(`/alert-preferences/games/${gameId}`, { token });
}

export function updateGameAlertOverride(
  token: string,
  gameId: number,
  alertType: string,
  payload: {
    is_enabled_override?: boolean | null;
    close_game_margin_threshold_override?: number | null;
    close_game_time_threshold_seconds_override?: number | null;
    inning_start_threshold_override?: number | null;
  },
): Promise<GameAlertPreferenceItem> {
  return apiRequest<GameAlertPreferenceItem>(`/alert-preferences/games/${gameId}/${alertType}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

export function clearGameAlertOverride(token: string, gameId: number, alertType: string): Promise<GameAlertPreferenceItem> {
  return apiRequest<GameAlertPreferenceItem>(`/alert-preferences/games/${gameId}/${alertType}`, {
    method: "DELETE",
    token,
  });
}

export function listAlertHistory(
  token: string,
  options?: { alertType?: AlertType; sinceHours?: number; limit?: number },
): Promise<{ items: AlertHistoryItem[] }> {
  const params = new URLSearchParams();
  if (options?.alertType) params.set("alert_type", options.alertType);
  if (options?.sinceHours) params.set("since_hours", String(options.sinceHours));
  if (options?.limit) params.set("limit", String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiRequest<{ items: AlertHistoryItem[] }>(`/alerts/history${suffix}`, { token });
}

export function sendDevTestEmail(
  token: string,
  payload: { league: League; alert_type: AlertType },
): Promise<{ id: number; game_id: number; league: League; alert_type: AlertType; delivery_status: DeliveryStatus }> {
  return apiRequest<{ id: number; game_id: number; league: League; alert_type: AlertType; delivery_status: DeliveryStatus }>(
    "/alerts/admin/test-email",
    {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    },
  );
}
