import { apiRequest } from "../client";
import type {
  NotificationSettings,
  PushSubscriptionPayload,
  PushSubscriptionStatus,
} from "../types";

export function getNotificationSettings(token: string): Promise<NotificationSettings> {
  return apiRequest<NotificationSettings>("/notification-settings", { token });
}

export function updateNotificationSettings(
  token: string,
  emailAlertsEnabled: boolean,
): Promise<NotificationSettings> {
  return apiRequest<NotificationSettings>("/notification-settings", {
    method: "PUT",
    token,
    body: JSON.stringify({ email_alerts_enabled: emailAlertsEnabled }),
  });
}

export function getPushSubscriptionStatus(
  token: string,
  endpoint: string,
): Promise<PushSubscriptionStatus> {
  return apiRequest<PushSubscriptionStatus>("/push-subscriptions/status", {
    method: "POST",
    token,
    body: JSON.stringify({ endpoint }),
  });
}

export function savePushSubscription(
  token: string,
  subscription: PushSubscriptionPayload,
): Promise<void> {
  return apiRequest<void>("/push-subscriptions", {
    method: "POST",
    token,
    body: JSON.stringify(subscription),
  });
}

export function deletePushSubscription(token: string, endpoint: string): Promise<void> {
  return apiRequest<void>("/push-subscriptions", {
    method: "DELETE",
    token,
    body: JSON.stringify({ endpoint }),
  });
}
