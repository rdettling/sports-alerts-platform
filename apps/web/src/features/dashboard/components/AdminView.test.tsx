import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
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

const leagueSettings: OpsAdminSummaryResponse["runtime"]["league_settings"] = [
  {
    league: "WNBA",
    sport: "basketball",
    label: "WNBA",
    badge_label: "WNBA",
    alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
    live_sync_interval_seconds: 120,
    default_test_matchup: ["NY", "LV"],
    is_enabled: true,
  },
  {
    league: "MLB",
    sport: "baseball",
    label: "MLB",
    badge_label: "MLB",
    alert_types: ["game_start", "inning_start", "extra_innings_start", "final_result"],
    live_sync_interval_seconds: 300,
    default_test_matchup: ["MIA", "TOR"],
    is_enabled: true,
  },
];

const baseSummary: OpsAdminSummaryResponse = {
  overview: {
    window: "24h",
    total_provider_calls: 12,
    provider_errors: 1,
    provider_rate_limits: 2,
    total_emails_attempted: 4,
    emails_sent: 3,
    emails_failed: 1,
    total_alerts_created: 3,
    last_updated_at: "2026-06-20T08:00:00Z",
  },
  providers: [
    {
      provider: "espn",
      total_calls: 8,
      success_calls: 8,
      error_calls: 0,
      rate_limited_calls: 0,
      calls_per_hour: 0.33,
      quota_limit_window: 5000,
      utilization_pct: 0.16,
      most_used_endpoint: "scoreboard",
    },
    {
      provider: "odds",
      total_calls: 2,
      success_calls: 1,
      error_calls: 0,
      rate_limited_calls: 1,
      calls_per_hour: 0.08,
      quota_limit_window: 1000,
      utilization_pct: 0.2,
      most_used_endpoint: "h2h",
    },
    {
      provider: "resend",
      total_calls: 2,
      success_calls: 1,
      error_calls: 1,
      rate_limited_calls: 0,
      calls_per_hour: 0.08,
      quota_limit_window: null,
      utilization_pct: null,
      most_used_endpoint: "resend_send_email",
    },
  ],
  delivery: {
    email_alerts: { attempted: 3, sent: 2, failed: 1 },
    push_alerts: { attempted: 0, sent: 0, failed: 0 },
    magic_links: { attempted: 1, sent: 1, failed: 0 },
    resend: { total_calls: 4, success_calls: 3, error_calls: 1, rate_limited_calls: 1 },
  },
  runtime: {
    scheduler_mode: "live",
    next_run_at: "2026-06-20T08:05:00Z",
    last_success_at: "2026-06-20T08:04:00Z",
    active_leagues: ["WNBA", "MLB"],
    league_settings: leagueSettings,
    jobs: [
      {
        job_type: "catalog_sync",
        league: "WNBA",
        status: "queued",
        next_run_at: "2026-06-20T09:00:00Z",
        last_success_at: "2026-06-20T08:00:00Z",
        backoff_until: null,
        last_error: null,
      },
      {
        job_type: "live_sync",
        league: "WNBA",
        status: "failed",
        next_run_at: "2026-06-20T08:05:00Z",
        last_success_at: "2026-06-20T08:04:00Z",
        backoff_until: "2026-06-20T08:15:00Z",
        last_error: "Provider timeout",
      },
      {
        job_type: "catalog_sync",
        league: "MLB",
        status: "queued",
        next_run_at: "2026-06-20T09:10:00Z",
        last_success_at: "2026-06-20T08:10:00Z",
        backoff_until: null,
        last_error: null,
      },
    ],
  },
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

  it("opens on Overview and surfaces activity, runtime issues, and Neon usage", async () => {
    renderAdmin();

    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("Provider calls").closest("article")).toHaveTextContent("12");
    expect(screen.getByText("Provider errors").closest("article")).toHaveClass("is-danger");
    expect(screen.getByText("Email success").closest("article")).toHaveTextContent("75%");
    expect(screen.getByText("1 job issue")).toHaveClass("is-danger");

    expect(await screen.findByText("2.00 CUh")).toBeInTheDocument();
    expect(screen.getByText("1.00h")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Neon" })).toHaveAttribute(
      "href",
      "https://example.com/neon",
    );
  });

  it("shows the telemetry window only on telemetry tabs and supports keyboard tabs", () => {
    renderAdmin();
    const windowSelect = screen.getByRole("combobox", { name: "Telemetry window" });
    fireEvent.change(windowSelect, { target: { value: "7d" } });
    expect(mocks.useAdminData).toHaveBeenLastCalledWith("token", "7d");

    const overview = screen.getByRole("tab", { name: "Overview" });
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Providers" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("combobox", { name: "Telemetry window" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Jobs" }));
    expect(screen.queryByRole("combobox", { name: "Telemetry window" })).toBeNull();
    expect(screen.getByRole("tabpanel", { name: "Jobs" })).toBeInTheDocument();
  });

  it("keeps existing content visible while refreshing and reports refresh failures", () => {
    mocks.useAdminData.mockReturnValue(
      adminData(null, { data: { summary: baseSummary }, isFetching: true }),
    );
    const view = renderAdmin();
    expect(screen.getByText("Refreshing…")).toBeInTheDocument();
    expect(screen.getByText("Provider calls")).toBeInTheDocument();
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
    expect(screen.getByText("Provider calls")).toBeInTheDocument();
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

  it("renders responsive provider rows and their empty state", () => {
    const view = renderAdmin();
    fireEvent.click(screen.getByRole("tab", { name: "Providers" }));

    const espn = screen.getByText("ESPN").closest("article");
    expect(espn).not.toBeNull();
    expect(within(espn!).getByText("scoreboard")).toBeInTheDocument();
    expect(within(espn!).getByText("0.33/hour")).toBeInTheDocument();
    expect(screen.getByText("Odds")).toBeInTheDocument();
    expect(screen.getByText("Resend")).toBeInTheDocument();
    view.unmount();

    const emptySummary = structuredClone(baseSummary);
    emptySummary.providers = [];
    mocks.useAdminData.mockReturnValue(adminData(emptySummary));
    renderAdmin();
    fireEvent.click(screen.getByRole("tab", { name: "Providers" }));
    expect(screen.getByText("No provider activity in this window.")).toBeInTheDocument();
  });

  it("shows all delivery groups, success rates, n/a, and failure emphasis", () => {
    renderAdmin();
    fireEvent.click(screen.getByRole("tab", { name: "Delivery" }));

    const email = screen.getByText("Alert Email").closest("article");
    const push = screen.getByText("Push").closest("article");
    const resend = screen.getByText("Resend").closest("article");
    expect(within(email!).getByText("67%")).toBeInTheDocument();
    expect(within(push!).getByText("n/a")).toBeInTheDocument();
    expect(screen.getByText("Magic Link")).toBeInTheDocument();
    expect(within(resend!).getByText("75%")).toBeInTheDocument();
    expect(within(resend!).getByText("Errors / 429s").parentElement).toHaveClass("is-danger");
  });

  it("shows job details, league switching, missing jobs, and empty leagues", () => {
    const view = renderAdmin();
    fireEvent.click(screen.getByRole("tab", { name: "Jobs" }));
    expect(screen.getByRole("button", { name: "WNBA" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Provider timeout")).toBeInTheDocument();
    expect(screen.getByText("Backoff until")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    expect(screen.getByRole("button", { name: "MLB" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("missing")).toBeInTheDocument();
    view.unmount();

    const emptySummary = structuredClone(baseSummary);
    emptySummary.runtime.league_settings.forEach((league) => {
      league.is_enabled = false;
    });
    mocks.useAdminData.mockReturnValue(adminData(emptySummary));
    renderAdmin();
    fireEvent.click(screen.getByRole("tab", { name: "Jobs" }));
    expect(screen.getByText("No enabled leagues are available.")).toBeInTheDocument();
  });
});
