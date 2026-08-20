import { apiRequest } from "../client";
import type {
  AlertHistoryItem,
  AlertPreference,
  AlertPreferenceGroup,
  AlertSettingsUpdate,
  AlertType,
  DeliveryStatus,
  GameAlertPreferenceItem,
  GameAlertPreferences,
  Competition,
  Sport,
} from "../types";

export function listAlertPreferences(token: string): Promise<AlertPreferenceGroup[]> {
  return apiRequest<AlertPreferenceGroup[]>("/alert-preferences", { token });
}

export function updateAlertPreference(
  token: string,
  sport: Sport,
  alertType: string,
  payload: AlertSettingsUpdate,
): Promise<AlertPreference> {
  return apiRequest<AlertPreference>(`/alert-preferences/sports/${sport}/${alertType}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

export function getGameAlertPreferences(
  token: string,
  gameId: number,
): Promise<GameAlertPreferences> {
  return apiRequest<GameAlertPreferences>(`/alert-preferences/games/${gameId}`, { token });
}

export function updateGameAlertSettings(
  token: string,
  gameId: number,
  alertType: string,
  payload: AlertSettingsUpdate,
): Promise<GameAlertPreferenceItem> {
  return apiRequest<GameAlertPreferenceItem>(`/alert-preferences/games/${gameId}/${alertType}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

export function resetGameAlertSettings(
  token: string,
  gameId: number,
  alertType: string,
): Promise<GameAlertPreferenceItem> {
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

export function sendAdminTestAlert(
  token: string,
  payload: { competition: Competition; alert_type: AlertType },
): Promise<{
  competition: Competition;
  alert_type: AlertType;
  deliveries: Array<{
    channel: string;
    status: DeliveryStatus;
    attempted_at: string | null;
  }>;
}> {
  return apiRequest<{
    competition: Competition;
    alert_type: AlertType;
    deliveries: Array<{
      channel: string;
      status: DeliveryStatus;
      attempted_at: string | null;
    }>;
  }>("/alerts/admin/test", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}
