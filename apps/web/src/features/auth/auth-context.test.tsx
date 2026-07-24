import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "./auth-context";

const meMock = vi.fn();

vi.mock("../../shared/api", () => ({
  me: (token: string) => meMock(token),
  startMagicLink: vi.fn(),
  verifyMagicLink: vi.fn(),
}));

function AuthState() {
  const { token, user } = useAuth();
  return <div>{token ?? "no-token"}|{user?.email ?? "no-user"}</div>;
}

describe("AuthProvider cross-tab sync", () => {
  beforeEach(() => {
    localStorage.clear();
    meMock.mockReset();
    meMock.mockResolvedValue({
      id: 1,
      email: "user@example.com",
      role: "user",
      created_at: "2026-01-01T00:00:00Z",
    });
  });

  it("loads a token written by another tab", async () => {
    render(<AuthProvider><AuthState /></AuthProvider>);
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
    render(<AuthProvider><AuthState /></AuthProvider>);
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
});
