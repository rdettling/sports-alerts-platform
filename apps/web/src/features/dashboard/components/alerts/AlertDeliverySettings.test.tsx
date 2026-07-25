import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AlertDeliverySettings } from "./AlertDeliverySettings";

const mocks = vi.hoisted(() => ({
  getNotificationSettings: vi.fn(),
  updateNotificationSettings: vi.fn(),
  savePushSubscription: vi.fn(),
  getCurrentPushSubscription: vi.fn(),
  pushIsSupported: vi.fn(),
  subscribeCurrentBrowser: vi.fn(),
}));

const emailSettings = {
  delivery_mode: "email" as const,
  subscription_count: 0,
  push_configured: true,
  vapid_public_key: "public-key",
};

vi.mock("../../../../shared/api", () => ({
  getNotificationSettings: mocks.getNotificationSettings,
  updateNotificationSettings: mocks.updateNotificationSettings,
  savePushSubscription: mocks.savePushSubscription,
}));

vi.mock("../../../../shared/lib/push-notifications", () => ({
  getCurrentPushSubscription: mocks.getCurrentPushSubscription,
  pushIsSupported: mocks.pushIsSupported,
  pushSubscriptionPayload: vi.fn((subscription) => subscription.payload),
  subscribeCurrentBrowser: mocks.subscribeCurrentBrowser,
}));

describe("AlertDeliverySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getNotificationSettings.mockResolvedValue(emailSettings);
    mocks.getCurrentPushSubscription.mockResolvedValue(null);
    mocks.pushIsSupported.mockReturnValue(true);
  });

  it("subscribes the browser before switching to Push", async () => {
    const subscription = {
      payload: {
        endpoint: "https://push.example/device",
        keys: { p256dh: "key", auth: "auth" },
      },
    };
    mocks.subscribeCurrentBrowser.mockResolvedValue(subscription);
    mocks.updateNotificationSettings.mockResolvedValue({
      ...emailSettings,
      delivery_mode: "push",
      subscription_count: 1,
    });
    render(<AlertDeliverySettings token="token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Push" }));

    await waitFor(() => {
      expect(mocks.subscribeCurrentBrowser).toHaveBeenCalledWith("public-key");
      expect(mocks.savePushSubscription).toHaveBeenCalledWith("token", subscription.payload);
      expect(mocks.updateNotificationSettings).toHaveBeenCalledWith("token", "push");
    });
    expect(screen.getByText(/This device is subscribed/)).toBeInTheDocument();
  });

  it("enables Push on a new device without changing the active global mode", async () => {
    const pushSettings = {
      ...emailSettings,
      delivery_mode: "push" as const,
      subscription_count: 1,
    };
    const subscription = {
      payload: {
        endpoint: "https://push.example/iphone",
        keys: { p256dh: "iphone-key", auth: "iphone-auth" },
      },
    };
    mocks.getNotificationSettings
      .mockResolvedValueOnce(pushSettings)
      .mockResolvedValueOnce({ ...pushSettings, subscription_count: 2 });
    mocks.subscribeCurrentBrowser.mockResolvedValue(subscription);
    render(<AlertDeliverySettings token="token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Enable on this device" }));

    await waitFor(() => {
      expect(mocks.subscribeCurrentBrowser).toHaveBeenCalledWith("public-key");
      expect(mocks.savePushSubscription).toHaveBeenCalledWith("token", subscription.payload);
    });
    expect(mocks.updateNotificationSettings).not.toHaveBeenCalled();
    expect(screen.getByText("This device is subscribed · 2 total")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Push" })).toHaveClass("active");
  });

  it("keeps the global mode unchanged when new-device enrollment is denied", async () => {
    mocks.getNotificationSettings.mockResolvedValue({
      ...emailSettings,
      delivery_mode: "push",
      subscription_count: 1,
    });
    mocks.subscribeCurrentBrowser.mockRejectedValue(new Error("Permission denied"));
    render(<AlertDeliverySettings token="token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Enable on this device" }));

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    expect(mocks.savePushSubscription).not.toHaveBeenCalled();
    expect(mocks.updateNotificationSettings).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Push" })).toHaveClass("active");
    expect(screen.getByText("This device is not subscribed")).toBeInTheDocument();
  });

  it("leaves the previous mode unchanged when browser subscription fails", async () => {
    mocks.subscribeCurrentBrowser.mockRejectedValue(new Error("Permission denied"));
    render(<AlertDeliverySettings token="token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Push" }));

    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
    expect(mocks.updateNotificationSettings).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Email" })).toHaveClass("active");
  });

  it("explains the Home Screen requirement when Push is unsupported", async () => {
    mocks.pushIsSupported.mockReturnValue(false);
    render(<AlertDeliverySettings token="token" />);

    expect(
      await screen.findByText(/On iPhone or iPad, add this site to your Home Screen/),
    ).toBeInTheDocument();
  });

  it("selecting Email clears server settings and unsubscribes this browser", async () => {
    const unsubscribe = vi.fn().mockResolvedValue(true);
    const subscription = {
      unsubscribe,
      payload: {
        endpoint: "https://push.example/device",
        keys: { p256dh: "key", auth: "auth" },
      },
    };
    mocks.getNotificationSettings.mockResolvedValue({
      ...emailSettings,
      delivery_mode: "both",
      subscription_count: 2,
    });
    mocks.getCurrentPushSubscription.mockResolvedValue(subscription);
    mocks.updateNotificationSettings.mockResolvedValue(emailSettings);
    render(<AlertDeliverySettings token="token" />);

    const emailButton = await screen.findByRole("button", { name: "Email" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Both" })).toHaveClass("active"));
    fireEvent.click(emailButton);

    await waitFor(() => {
      expect(mocks.updateNotificationSettings).toHaveBeenCalledWith("token", "email");
      expect(unsubscribe).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByRole("button", { name: "Email" })).toHaveClass("active");
  });
});
