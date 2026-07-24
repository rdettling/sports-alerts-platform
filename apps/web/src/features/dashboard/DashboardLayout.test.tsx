import { MemoryRouter, Route, Routes } from "react-router-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardLayout } from "./DashboardLayout";

const logout = vi.fn();
let authState: {
  token: string | null;
  user: { email: string; role: "user" | "admin" } | null;
} = {
  token: "token",
  user: { email: "user@example.com", role: "admin" },
};

vi.mock("../auth/auth-context", () => ({
  useAuth: () => ({
    ...authState,
    logout,
  }),
}));

vi.mock("../auth/SignInModal", () => ({
  SignInModal: ({ isOpen }: { isOpen: boolean }) => isOpen ? <div role="dialog">Sign-in modal</div> : null,
}));

vi.mock("./components/GamesView", () => ({
  GamesView: ({ onSignInRequired }: { onSignInRequired: () => void }) => (
    <div>Games view<button onClick={onSignInRequired}>Guest follow</button></div>
  ),
}));

vi.mock("./components/FollowingView", () => ({
  FollowingView: () => <div>Following view</div>,
}));

vi.mock("./components/AlertsView", () => ({
  AlertsView: () => <div>Alerts view</div>,
}));

vi.mock("./components/AdminView", () => ({
  AdminView: () => <div>Admin view</div>,
}));

function renderLayout(entry = "/games") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="*" element={<DashboardLayout />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DashboardLayout", () => {
  beforeEach(() => {
    logout.mockClear();
    authState = {
      token: "token",
      user: { email: "user@example.com", role: "admin" },
    };
  });

  it("renders authenticated navigation and logout", () => {
    renderLayout();

    expect(screen.getByRole("link", { name: /games/i })).toHaveClass("active");
    expect(screen.getByRole("link", { name: /following/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /alerts/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /admin/i })).toBeInTheDocument();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("shows only Games and Sign in to a guest", () => {
    authState = { token: null, user: null };
    renderLayout();

    expect(screen.getByRole("link", { name: /games/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /following/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /alerts/i })).toBeNull();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Sign-in modal");
  });

  it("opens sign-in when a guest attempts to follow", () => {
    authState = { token: null, user: null };
    renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "Guest follow" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("redirects a guest away from protected routes", async () => {
    authState = { token: null, user: null };
    renderLayout("/alerts");
    expect(await screen.findByText("Games view")).toBeInTheDocument();
  });
});
