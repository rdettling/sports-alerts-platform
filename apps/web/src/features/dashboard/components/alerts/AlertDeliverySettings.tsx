import { useEffect, useState } from "react";

import {
  deletePushSubscription,
  getNotificationSettings,
  getPushSubscriptionStatus,
  savePushSubscription,
  updateNotificationSettings,
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
    setSettings(currentSettings);
    if (!pushSupported) {
      setDeviceSubscribed(false);
      return;
    }
    const currentSubscription = await getCurrentPushSubscription();
    if (!currentSubscription) {
      setDeviceSubscribed(false);
      return;
    }
    const status = await getPushSubscriptionStatus(
      token,
      pushSubscriptionPayload(currentSubscription).endpoint,
    );
    setDeviceSubscribed(status.is_subscribed);
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

  const toggleEmailAlerts = async () => {
    if (!settings) return;
    setError(null);
    setBusy(true);
    try {
      setSettings(await updateNotificationSettings(token, !settings.email_alerts_enabled));
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  const togglePushThisDevice = async () => {
    if (!settings) return;
    setError(null);
    setBusy(true);
    try {
      if (deviceSubscribed) {
        const currentSubscription = await getCurrentPushSubscription();
        if (currentSubscription) {
          await deletePushSubscription(
            token,
            pushSubscriptionPayload(currentSubscription).endpoint,
          );
          await currentSubscription.unsubscribe().catch(() => false);
        }
        setDeviceSubscribed(false);
      } else {
        await subscribeThisDevice();
      }
      setSettings(await getNotificationSettings(token));
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="alerts-delivery-panel surface" aria-labelledby="alert-delivery-title">
      <div className="alerts-delivery-header">
        <h2 id="alert-delivery-title">Delivery</h2>
        <p>Choose where sports alerts reach you.</p>
        {error ? (
          <p className="error alerts-delivery-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
      <div className="alerts-delivery-options">
        <div className="alerts-delivery-option">
          <div className="alerts-delivery-option-copy">
            <strong>Email alerts</strong>
            <span>Sports alerts only. Sign-in emails are still sent when requested.</span>
          </div>
          <button
            className={`alert-toggle alerts-delivery-switch ${settings?.email_alerts_enabled ? "on" : "off"}`}
            type="button"
            role="switch"
            aria-label="Email alerts"
            aria-checked={settings?.email_alerts_enabled ?? false}
            disabled={busy || !settings}
            onClick={toggleEmailAlerts}
          >
            <span className="alert-toggle-label" aria-hidden>
              {settings?.email_alerts_enabled ? "On" : "Off"}
            </span>
            <span className="alert-toggle-track" aria-hidden>
              <span className="alert-toggle-thumb" />
            </span>
          </button>
        </div>
        <div className="alerts-delivery-option">
          <div className="alerts-delivery-option-copy">
            <strong>Push on this device</strong>
            <span role="status">
              {!settings
                ? "Loading push settings..."
                : !pushSupported
                  ? "Unavailable here. On iPhone or iPad, add this site to your Home Screen and open it there."
                  : !settings.push_configured
                    ? "Push is not configured yet."
                    : `${deviceSubscribed ? "On" : "Off"} for this device · ${settings.push_subscription_count} ${settings.push_subscription_count === 1 ? "device" : "devices"} enabled`}
            </span>
          </div>
          <button
            className={`alert-toggle alerts-delivery-switch ${deviceSubscribed ? "on" : "off"}`}
            type="button"
            role="switch"
            aria-label="Push on this device"
            aria-checked={deviceSubscribed}
            disabled={busy || !settings || !pushSupported || !settings.push_configured}
            onClick={togglePushThisDevice}
          >
            <span className="alert-toggle-label" aria-hidden>
              {deviceSubscribed ? "On" : "Off"}
            </span>
            <span className="alert-toggle-track" aria-hidden>
              <span className="alert-toggle-thumb" />
            </span>
          </button>
        </div>
      </div>
      {settings && !settings.email_alerts_enabled && settings.push_subscription_count === 0 ? (
        <p className="alerts-delivery-warning" role="status">
          Alerts are currently off. Enable email or push on a device to receive them.
        </p>
      ) : null}
    </section>
  );
}
