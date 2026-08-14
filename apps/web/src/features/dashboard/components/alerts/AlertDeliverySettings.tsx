import { useEffect, useState } from "react";

import {
  getNotificationSettings,
  savePushSubscription,
  updateNotificationSettings,
  type DeliveryMode,
  type NotificationSettings,
} from "../../../../shared/api";
import {
  getCurrentPushSubscription,
  pushIsSupported,
  pushSubscriptionPayload,
  subscribeCurrentBrowser,
} from "../../../../shared/lib/push-notifications";
import { messageFromUnknown } from "../../../../shared/lib/dashboard-ui";

export function AlertDeliverySettings({ token }: { token: string }) {
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [deviceSubscribed, setDeviceSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pushSupported = pushIsSupported();

  const load = async () => {
    const currentSettings = await getNotificationSettings(token);
    let currentSubscription: PushSubscription | null = null;
    if (pushSupported) {
      currentSubscription = await getCurrentPushSubscription();
      if (currentSubscription && currentSettings.delivery_mode !== "email") {
        await savePushSubscription(token, pushSubscriptionPayload(currentSubscription));
      }
    }
    setDeviceSubscribed(Boolean(currentSubscription));
    setSettings(
      currentSubscription && currentSettings.delivery_mode !== "email"
        ? await getNotificationSettings(token)
        : currentSettings,
    );
  };

  useEffect(() => {
    load().catch((loadError) => setError(messageFromUnknown(loadError)));
  }, [token]);

  const subscribeThisDevice = async () => {
    if (!settings?.push_configured || !settings.vapid_public_key) {
      throw new Error("Push notifications are not configured yet.");
    }
    const subscription = await subscribeCurrentBrowser(settings.vapid_public_key);
    await savePushSubscription(token, pushSubscriptionPayload(subscription));
    setDeviceSubscribed(true);
  };

  const enablePushThisDevice = async () => {
    setError(null);
    setBusy(true);
    try {
      await subscribeThisDevice();
      setSettings(await getNotificationSettings(token));
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  const changeDeliveryMode = async (mode: DeliveryMode) => {
    if (!settings || mode === settings.delivery_mode) return;
    setError(null);
    setBusy(true);
    try {
      if (mode === "email") {
        const currentSubscription = await getCurrentPushSubscription().catch(() => null);
        const nextSettings = await updateNotificationSettings(token, "email");
        await currentSubscription?.unsubscribe().catch(() => false);
        setDeviceSubscribed(false);
        setSettings(nextSettings);
        return;
      }
      await subscribeThisDevice();
      setSettings(await updateNotificationSettings(token, mode));
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="alerts-delivery-bar surface" aria-labelledby="alert-delivery-title">
      <div className="alerts-delivery-copy">
        <h2 id="alert-delivery-title">Delivery</h2>
        <p>Choose how you receive alerts. Email is the default.</p>
        {error ? (
          <p className="error alerts-delivery-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
      <div className="alerts-delivery-controls">
        <div className="alerts-delivery-modes" role="group" aria-label="Alert delivery method">
          {(["email", "push", "both"] as const).map((mode) => (
            <button
              key={mode}
              className={`alerts-delivery-mode ${settings?.delivery_mode === mode ? "active" : ""}`.trim()}
              type="button"
              aria-pressed={settings?.delivery_mode === mode}
              disabled={
                busy ||
                !settings ||
                (mode !== "email" && (!pushSupported || !settings.push_configured))
              }
              onClick={() => changeDeliveryMode(mode)}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
        <div className="alerts-device-row">
          <span className="alerts-device-status" role="status">
            {!settings
              ? "Loading delivery settings..."
              : !pushSupported
                ? "Push is unavailable here. On iPhone or iPad, add this site to your Home Screen and open it there."
                : !settings.push_configured
                  ? "Push is not configured yet."
                  : deviceSubscribed
                    ? `This device is subscribed · ${settings.subscription_count} total`
                    : "This device is not subscribed"}
          </span>
          {pushSupported &&
          settings?.push_configured &&
          settings.delivery_mode !== "email" &&
          !deviceSubscribed ? (
            <button
              className="alerts-device-action text-action"
              type="button"
              disabled={busy}
              onClick={enablePushThisDevice}
            >
              Enable on this device
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}
