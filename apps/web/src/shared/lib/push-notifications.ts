import type { PushSubscriptionPayload } from "../api";

export function pushIsSupported(): boolean {
  const navigatorWithStandalone = navigator as Navigator & { standalone?: boolean };
  const isAppleMobile =
    /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isStandalone =
    navigatorWithStandalone.standalone === true ||
    window.matchMedia?.("(display-mode: standalone)").matches === true;
  return (
    (!isAppleMobile || isStandalone) &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export async function registerNotificationServiceWorker(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.register("/service-worker.js", { updateViaCache: "none" });
}

export async function getCurrentPushSubscription(): Promise<PushSubscription | null> {
  if (!pushIsSupported()) return null;
  const registration = await registerNotificationServiceWorker();
  return registration.pushManager.getSubscription();
}

function applicationServerKey(publicKey: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (publicKey.length % 4)) % 4);
  const base64 = (publicKey + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index);
  }
  return bytes;
}

export async function subscribeCurrentBrowser(publicKey: string): Promise<PushSubscription> {
  if (!pushIsSupported()) {
    throw new Error("Push notifications are not supported in this browser.");
  }
  const permission =
    Notification.permission === "default"
      ? await Notification.requestPermission()
      : Notification.permission;
  if (permission !== "granted") {
    throw new Error("Notification permission was not granted.");
  }
  const registration = await registerNotificationServiceWorker();
  const existing = await registration.pushManager.getSubscription();
  return (
    existing ??
    registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: applicationServerKey(publicKey),
    })
  );
}

export function pushSubscriptionPayload(subscription: PushSubscription): PushSubscriptionPayload {
  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) {
    throw new Error("The browser returned an incomplete push subscription.");
  }
  return {
    endpoint: json.endpoint,
    keys: {
      p256dh: json.keys.p256dh,
      auth: json.keys.auth,
    },
  };
}
