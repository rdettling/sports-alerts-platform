import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AdminView } from "./AdminView";

const getOpsNeonUsageMock = vi.fn(async () => ({
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
}));

vi.mock("../../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../../shared/api")>("../../../shared/api");
  return {
    ...actual,
    getOpsNeonUsage: (...args: Parameters<typeof getOpsNeonUsageMock>) => getOpsNeonUsageMock(...args),
  };
});

vi.mock("../hooks/useAdminData", () => ({
  useAdminData: vi.fn(() => ({
    isLoading: false,
    isFetching: false,
    error: null,
    data: {
      summary: {
        overview: {
          window: "24h",
          total_provider_calls: 12,
          provider_errors: 1,
          provider_rate_limits: 0,
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
          alerts: { attempted: 3, sent: 2, failed: 1 },
          magic_links: { attempted: 1, sent: 1, failed: 0 },
          resend: { total_calls: 4, success_calls: 3, error_calls: 1, rate_limited_calls: 0 },
        },
        runtime: {
          scheduler_mode: "live",
          next_run_at: "2026-06-20T08:05:00Z",
          last_success_at: "2026-06-20T08:04:00Z",
          active_leagues: ["NBA", "WNBA", "MLB", "MLS", "WORLD_CUP"],
          league_settings: [
            { league: "NBA", sport: "basketball", label: "NBA", badge_label: "NBA", alert_types: ["game_start"], live_sync_interval_seconds: 120, default_test_matchup: ["ATL", "BOS"], is_enabled: true },
            { league: "WNBA", sport: "basketball", label: "WNBA", badge_label: "WNBA", alert_types: ["game_start"], live_sync_interval_seconds: 120, default_test_matchup: ["NY", "LV"], is_enabled: true },
            { league: "MLB", sport: "baseball", label: "MLB", badge_label: "MLB", alert_types: ["game_start"], live_sync_interval_seconds: 300, default_test_matchup: ["MIA", "TOR"], is_enabled: true },
            { league: "MLS", sport: "soccer", label: "MLS", badge_label: "MLS", alert_types: ["game_start"], live_sync_interval_seconds: 180, default_test_matchup: ["LAFC", "LA"], is_enabled: true },
            { league: "WORLD_CUP", sport: "soccer", label: "World Cup", badge_label: "WC", alert_types: ["game_start"], live_sync_interval_seconds: 180, default_test_matchup: ["MEX", "USA"], is_enabled: true },
          ],
          jobs: [
            {
              job_type: "catalog_sync",
              league: "NBA",
              status: "queued",
              next_run_at: "2026-06-20T09:00:00Z",
              last_success_at: "2026-06-20T08:00:00Z",
              backoff_until: null,
              last_error: null,
            },
            {
              job_type: "live_sync",
              league: "NBA",
              status: "queued",
              next_run_at: "2026-06-20T08:05:00Z",
              last_success_at: "2026-06-20T08:04:00Z",
              backoff_until: null,
              last_error: null,
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
            {
              job_type: "live_sync",
              league: "WORLD_CUP",
              status: "queued",
              next_run_at: "2026-06-20T08:05:00Z",
              last_success_at: "2026-06-20T08:04:00Z",
              backoff_until: null,
              last_error: null,
            },
          ],
        },
      },
    },
  })),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("AdminView", () => {
  it("shows the database tab by default", async () => {
    render(<AdminView token="token" />, { wrapper });

    expect(screen.getByRole("button", { name: "Database" })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(getOpsNeonUsageMock).toHaveBeenCalledWith("token"));
    await waitFor(() => expect(screen.getByText("Open Neon dashboard")).toBeInTheDocument());
  });

  it("shows jobs grouped by enabled league", async () => {
    render(<AdminView token="token" />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: "Jobs" }));

    await waitFor(() => expect(screen.getAllByText("NBA").length).toBeGreaterThan(0));

    const nbaSelector = screen.getAllByText("NBA")[0].closest("button");
    const mlbSelector = screen.getAllByText("MLB")[0].closest("button");

    expect(nbaSelector).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "NBA" })).toBeInTheDocument();
    expect(screen.getByText("Catalog sync")).toBeInTheDocument();
    expect(screen.getByText("Live sync")).toBeInTheDocument();
    expect(screen.getAllByText("Previous sync").length).toBeGreaterThan(0);

    expect(mlbSelector).not.toBeNull();
    fireEvent.click(mlbSelector!);

    expect(mlbSelector).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "MLB" })).toBeInTheDocument();
  });

  it("shows the redesigned delivery cards", async () => {
    render(<AdminView token="token" />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: "Delivery" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Delivery" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Alert emails" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Magic links" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Resend API" })).toBeInTheDocument();
    expect(screen.getAllByText("Success rate").length).toBeGreaterThan(0);
  });
});
