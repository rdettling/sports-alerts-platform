import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type OpsAdminSummaryResponse } from "../../../shared/api";
import { AdminView } from "./AdminView";

const mocks = vi.hoisted(() => ({
  getOpsNeonUsage: vi.fn(),
  useAdminData: vi.fn(),
}));

vi.mock("../../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../../shared/api")>("../../../shared/api");
  return { ...actual, getOpsNeonUsage: mocks.getOpsNeonUsage };
});

vi.mock("../hooks/useAdminData", () => ({ useAdminData: mocks.useAdminData }));

const leagueSettings: OpsAdminSummaryResponse["league_settings"] = [
  {
    league: "WNBA",
    sport: "basketball",
    label: "WNBA",
    badge_label: "WNBA",
    alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
  {
    league: "MLB",
    sport: "baseball",
    label: "MLB",
    badge_label: "MLB",
    alert_types: ["game_start", "inning_start", "extra_innings_start", "final_result"],
    live_sync_interval_seconds: 300,
    is_enabled: true,
  },
];

const baseSummary: OpsAdminSummaryResponse = {
  overview: {
    window: "24h",
    total_alerts_created: 3,
    last_updated_at: "2026-06-20T08:00:00Z",
  },
  delivery: {
    email_alerts: { attempted: 3, sent: 2, failed: 1 },
    push_alerts: { attempted: 0, sent: 0, failed: 0 },
  },
  league_settings: leagueSettings,
};

function adminData(
  summary: OpsAdminSummaryResponse | null = structuredClone(baseSummary),
  overrides: Record<string, unknown> = {},
) {
  return {
    data: summary ? { summary } : undefined,
    isLoading: false,
    isFetching: false,
    error: null,
    ...overrides,
  };
}

function renderAdmin() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminView token="token" />
    </QueryClientProvider>,
  );
}

describe("AdminView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useAdminData.mockReturnValue(adminData());
    mocks.getOpsNeonUsage.mockResolvedValue({
      available: true,
      project_id: "project",
      project_name: "Project",
      dashboard_url: "https://example.com/neon",
      consumption_period_start: "2026-06-01T00:00:00Z",
      consumption_period_end: "2026-06-30T00:00:00Z",
      cpu_used_sec: 7200,
      active_time_sec: 3600,
      compute_last_active_at: "2026-06-20T08:00:00Z",
      avg_cu_while_active: 2,
      message: null,
    });
  });

  it("opens on Overview and surfaces activity and Neon usage", async () => {
    renderAdmin();

    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Overview", "Tools"]);
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("Alerts created").closest("article")).toHaveTextContent("3");
    expect(screen.getByText("Email sent / attempted").closest("article")).toHaveTextContent(
      "2 / 3",
    );
    expect(screen.getByText("Email failures").closest("article")).toHaveClass("is-danger");
    expect(screen.getByText("Push sent / attempted").closest("article")).toHaveTextContent("0 / 0");
    expect(screen.getByText("Push failures").closest("article")).not.toHaveClass("is-danger");
    expect(await screen.findByText("2.00 CUh")).toBeInTheDocument();
    expect(screen.getByText("1.00h")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Neon" })).toHaveAttribute(
      "href",
      "https://example.com/neon",
    );
  });

  it("shows the activity window only on Overview and supports keyboard tabs", () => {
    renderAdmin();
    const windowSelect = screen.getByRole("combobox", { name: "Activity window" });
    fireEvent.change(windowSelect, { target: { value: "7d" } });
    expect(mocks.useAdminData).toHaveBeenLastCalledWith("token", "7d");

    const overview = screen.getByRole("tab", { name: "Overview" });
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Tools" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("combobox", { name: "Activity window" })).toBeNull();
    expect(screen.getByRole("tabpanel", { name: "Tools" })).toBeInTheDocument();
  });

  it("keeps existing content visible while refreshing and reports refresh failures", () => {
    mocks.useAdminData.mockReturnValue(
      adminData(null, { data: { summary: baseSummary }, isFetching: true }),
    );
    const view = renderAdmin();
    expect(screen.getByText("Refreshing…")).toBeInTheDocument();
    expect(screen.getByText("Alerts created")).toBeInTheDocument();
    view.unmount();

    mocks.useAdminData.mockReturnValue(
      adminData(null, {
        data: { summary: baseSummary },
        error: new Error("Refresh unavailable"),
      }),
    );
    renderAdmin();
    expect(screen.getByText("Refresh failed")).toBeInTheDocument();
    expect(screen.getByText("Refresh unavailable")).toBeInTheDocument();
    expect(screen.getByText("Alerts created")).toBeInTheDocument();
  });

  it("shows initial loading and error states", () => {
    mocks.useAdminData.mockReturnValue(adminData(null, { isLoading: true }));
    const loading = renderAdmin();
    expect(screen.getByText("Loading admin data…")).toBeInTheDocument();
    loading.unmount();

    mocks.useAdminData.mockReturnValue(adminData(null, { error: new Error("Admin unavailable") }));
    renderAdmin();
    expect(screen.getByText("Admin unavailable")).toBeInTheDocument();
  });
});
