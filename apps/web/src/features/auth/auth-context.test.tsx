import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "./auth-context";

const meMock = vi.fn();
const deletePushSubscriptionMock = vi.fn();
const getCurrentPushSubscriptionMock = vi.fn();

vi.mock("../../shared/api", () => ({
  deletePushSubscription: (...args: unknown[]) => deletePushSubscriptionMock(...args),
  me: (token: string) => meMock(token),
  startMagicLink: vi.fn(),
  verifyMagicLink: vi.fn(),
}));

vi.mock("../../shared/lib/push-notifications", () => ({
  getCurrentPushSubscription: () => getCurrentPushSubscriptionMock(),
  pushSubscriptionPayload: () => ({
    endpoint: "https://push.example/current-device",
    keys: { p256dh: "key", auth: "auth" },
  }),
}));

function AuthState() {
  const { token, user, logout } = useAuth();
  return (
    <div>
      {token ?? "no-token"}|{user?.email ?? "no-user"}
      <button type="button" onClick={() => void logout()}>
        Log out
      </button>
    </div>
  );
}

describe("AuthProvider cross-tab sync", () => {
  beforeEach(() => {
    localStorage.clear();
    meMock.mockReset();
    deletePushSubscriptionMock.mockReset();
    getCurrentPushSubscriptionMock.mockReset();
    getCurrentPushSubscriptionMock.mockResolvedValue(null);
    meMock.mockResolvedValue({
      id: 1,
      email: "user@example.com",
      role: "user",
      created_at: "2026-01-01T00:00:00Z",
    });
  });

  it("loads a token written by another tab", async () => {
    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );
    expect(await screen.findByText("no-token|no-user")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "sports_alerts_token",
          newValue: "new-token",
          storageArea: localStorage,
        }),
      );
    });

    await waitFor(() => expect(meMock).toHaveBeenCalledWith("new-token"));
    expect(await screen.findByText("new-token|user@example.com")).toBeInTheDocument();
  });

  it("clears authentication when another tab logs out", async () => {
    localStorage.setItem("sports_alerts_token", "existing-token");
    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );
    expect(await screen.findByText("existing-token|user@example.com")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "sports_alerts_token",
          newValue: null,
          storageArea: localStorage,
        }),
      );
    });

    expect(await screen.findByText("no-token|no-user")).toBeInTheDocument();
  });

  it("removes only the current browser subscription on logout", async () => {
    const unsubscribe = vi.fn().mockResolvedValue(true);
    getCurrentPushSubscriptionMock.mockResolvedValue({ unsubscribe });
    deletePushSubscriptionMock.mockResolvedValue(undefined);
    localStorage.setItem("sports_alerts_token", "existing-token");
    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );
    expect(await screen.findByText(/existing-token\|user@example.com/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => {
      expect(deletePushSubscriptionMock).toHaveBeenCalledWith(
        "existing-token",
        "https://push.example/current-device",
      );
      expect(unsubscribe).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText(/no-token\|no-user/)).toBeInTheDocument();
  });
});
