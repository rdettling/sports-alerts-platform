import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AlertDeliverySettings } from "./AlertDeliverySettings";

const mocks = vi.hoisted(() => ({
  deletePushSubscription: vi.fn(),
  getNotificationSettings: vi.fn(),
  getPushSubscriptionStatus: vi.fn(),
  updateNotificationSettings: vi.fn(),
  savePushSubscription: vi.fn(),
  getCurrentPushSubscription: vi.fn(),
  pushIsSupported: vi.fn(),
  subscribeCurrentBrowser: vi.fn(),
}));

const emailSettings = {
  email_alerts_enabled: true,
  push_subscription_count: 0,
  push_configured: true,
  vapid_public_key: "public-key",
};

function subscription(endpoint = "https://push.example/device") {
  return {
    unsubscribe: vi.fn().mockResolvedValue(true),
    payload: {
      endpoint,
      keys: { p256dh: "key", auth: "auth" },
    },
  };
}

vi.mock("../../../../shared/api", () => ({
  deletePushSubscription: mocks.deletePushSubscription,
  getNotificationSettings: mocks.getNotificationSettings,
  getPushSubscriptionStatus: mocks.getPushSubscriptionStatus,
  updateNotificationSettings: mocks.updateNotificationSettings,
  savePushSubscription: mocks.savePushSubscription,
}));

vi.mock("../../../../shared/lib/push-notifications", () => ({
  getCurrentPushSubscription: mocks.getCurrentPushSubscription,
  pushIsSupported: mocks.pushIsSupported,
  pushSubscriptionPayload: vi.fn((current) => current.payload),
  subscribeCurrentBrowser: mocks.subscribeCurrentBrowser,
}));

describe("AlertDeliverySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getNotificationSettings.mockResolvedValue(emailSettings);
    mocks.getCurrentPushSubscription.mockResolvedValue(null);
    mocks.getPushSubscriptionStatus.mockResolvedValue({ is_subscribed: false });
    mocks.pushIsSupported.mockReturnValue(true);
  });

  it("loads current-device status without silently registering the browser", async () => {
    const currentSubscription = subscription();
    mocks.getCurrentPushSubscription.mockResolvedValue(currentSubscription);
    mocks.getPushSubscriptionStatus.mockResolvedValue({ is_subscribed: true });
    mocks.getNotificationSettings.mockResolvedValue({
      ...emailSettings,
      push_subscription_count: 1,
    });

    render(<AlertDeliverySettings token="token" />);

    expect(await screen.findByText("On for this device · 1 device enabled")).toBeInTheDocument();
    expect(mocks.getPushSubscriptionStatus).toHaveBeenCalledWith(
      "token",
      currentSubscription.payload.endpoint,
    );
    expect(mocks.savePushSubscription).not.toHaveBeenCalled();
  });

  it("keeps a stale local browser subscription off until the user enables it", async () => {
    mocks.getCurrentPushSubscription.mockResolvedValue(subscription());

    render(<AlertDeliverySettings token="token" />);

    expect(await screen.findByText("Off for this device · 0 devices enabled")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Push on this device" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(mocks.savePushSubscription).not.toHaveBeenCalled();
  });

  it("toggles email independently from push", async () => {
    mocks.updateNotificationSettings.mockResolvedValue({
      ...emailSettings,
      email_alerts_enabled: false,
    });
    render(<AlertDeliverySettings token="token" />);

    fireEvent.click(await screen.findByRole("switch", { name: "Email alerts" }));

    await waitFor(() =>
      expect(mocks.updateNotificationSettings).toHaveBeenCalledWith("token", false),
    );
    expect(mocks.savePushSubscription).not.toHaveBeenCalled();
    expect(screen.getByText(/Alerts are currently off/)).toBeInTheDocument();
  });

  it("enables push on this device and refreshes the device count", async () => {
    const currentSubscription = subscription();
    mocks.subscribeCurrentBrowser.mockResolvedValue(currentSubscription);
    mocks.getNotificationSettings
      .mockResolvedValueOnce(emailSettings)
      .mockResolvedValueOnce({ ...emailSettings, push_subscription_count: 1 });
    render(<AlertDeliverySettings token="token" />);

    fireEvent.click(await screen.findByRole("switch", { name: "Push on this device" }));

    await waitFor(() => {
      expect(mocks.subscribeCurrentBrowser).toHaveBeenCalledWith("public-key");
      expect(mocks.savePushSubscription).toHaveBeenCalledWith("token", currentSubscription.payload);
    });
    expect(screen.getByText("On for this device · 1 device enabled")).toBeInTheDocument();
    expect(mocks.updateNotificationSettings).not.toHaveBeenCalled();
  });

  it("disables only this device and refreshes the device count", async () => {
    const currentSubscription = subscription();
    mocks.getCurrentPushSubscription.mockResolvedValue(currentSubscription);
    mocks.getPushSubscriptionStatus.mockResolvedValue({ is_subscribed: true });
    mocks.getNotificationSettings
      .mockResolvedValueOnce({ ...emailSettings, push_subscription_count: 2 })
      .mockResolvedValueOnce({ ...emailSettings, push_subscription_count: 1 });
    render(<AlertDeliverySettings token="token" />);

    const pushSwitch = await screen.findByRole("switch", { name: "Push on this device" });
    await waitFor(() => expect(pushSwitch).toHaveAttribute("aria-checked", "true"));
    fireEvent.click(pushSwitch);

    await waitFor(() => {
      expect(mocks.deletePushSubscription).toHaveBeenCalledWith(
        "token",
        currentSubscription.payload.endpoint,
      );
      expect(currentSubscription.unsubscribe).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("Off for this device · 1 device enabled")).toBeInTheDocument();
  });

  it("leaves push off when notification permission is denied", async () => {
    mocks.subscribeCurrentBrowser.mockRejectedValue(new Error("Permission denied"));
    render(<AlertDeliverySettings token="token" />);

    fireEvent.click(await screen.findByRole("switch", { name: "Push on this device" }));

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    expect(mocks.savePushSubscription).not.toHaveBeenCalled();
    expect(screen.getByRole("switch", { name: "Push on this device" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("explains the Home Screen requirement when push is unsupported", async () => {
    mocks.pushIsSupported.mockReturnValue(false);
    render(<AlertDeliverySettings token="token" />);

    expect(
      await screen.findByText(/On iPhone or iPad, add this site to your Home Screen/),
    ).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Push on this device" })).toBeDisabled();
  });

  it("disables the push switch when server push is not configured", async () => {
    mocks.getNotificationSettings.mockResolvedValue({
      ...emailSettings,
      push_configured: false,
      vapid_public_key: null,
    });
    render(<AlertDeliverySettings token="token" />);

    expect(await screen.findByText("Push is not configured yet.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Push on this device" })).toBeDisabled();
  });
});
