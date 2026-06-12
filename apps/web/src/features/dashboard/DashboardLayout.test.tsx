import { MemoryRouter, Route, Routes } from "react-router-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardLayout } from "./DashboardLayout";

const logout = vi.fn();

vi.mock("../auth/auth-context", () => ({
  useAuth: () => ({
    token: "token",
    user: { email: "user@example.com", role: "admin" },
    logout,
  }),
}));

vi.mock("./hooks/useDashboardSyncItems", () => ({
  useDashboardSyncItems: () => [
    { key: "catalog", label: "Catalog", value: "Just now" },
    { key: "nba", label: "NBA", value: "2m ago" },
  ],
}));

vi.mock("./components/GamesView", () => ({
  GamesView: () => <div>Games view</div>,
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

describe("DashboardLayout", () => {
  it("renders the shared shell content and active route navigation", () => {
    render(
      <MemoryRouter initialEntries={["/games"]}>
        <Routes>
          <Route path="*" element={<DashboardLayout />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Live Game Alerts")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Dashboard sections" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /games/i })).toHaveClass("active");
    expect(screen.getByLabelText("Data sync status")).toBeInTheDocument();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
    expect(screen.getByText("Games view")).toBeInTheDocument();
  });

  it("keeps the logout control wired", () => {
    render(
      <MemoryRouter initialEntries={["/alerts"]}>
        <Routes>
          <Route path="*" element={<DashboardLayout />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));
    expect(logout).toHaveBeenCalledTimes(1);
  });
});
