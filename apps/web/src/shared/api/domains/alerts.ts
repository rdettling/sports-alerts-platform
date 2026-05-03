import { apiRequest } from "../client";
import type { AlertHistoryItem, AlertPreference, AlertType, DeliveryStatus } from "../types";

export function listAlertPreferences(token: string): Promise<AlertPreference[]> {
  return apiRequest<AlertPreference[]>("/alert-preferences", { token });
}

export function updateAlertPreference(
  token: string,
  alertType: string,
  payload: {
    is_enabled?: boolean;
    close_game_margin_threshold?: number;
    close_game_time_threshold_seconds?: number;
  },
): Promise<AlertPreference> {
  return apiRequest<AlertPreference>(`/alert-preferences/${alertType}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
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
  payload: { alert_type: AlertType },
): Promise<{ id: number; game_id: number; alert_type: AlertType; delivery_status: DeliveryStatus }> {
  return apiRequest<{ id: number; game_id: number; alert_type: AlertType; delivery_status: DeliveryStatus }>(
    "/alerts/admin/test-email",
    {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    },
  );
}
