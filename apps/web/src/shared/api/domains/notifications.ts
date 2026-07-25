import { apiRequest } from "../client";
import type { DeliveryMode, NotificationSettings, PushSubscriptionPayload } from "../types";

export function getNotificationSettings(token: string): Promise<NotificationSettings> {
  return apiRequest<NotificationSettings>("/notification-settings", { token });
}

export function updateNotificationSettings(
  token: string,
  deliveryMode: DeliveryMode,
): Promise<NotificationSettings> {
  return apiRequest<NotificationSettings>("/notification-settings", {
    method: "PUT",
    token,
    body: JSON.stringify({ delivery_mode: deliveryMode }),
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
