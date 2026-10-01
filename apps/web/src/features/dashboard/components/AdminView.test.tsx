import {
  focusManager,
  onlineManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { type OpsAdminSummaryResponse } from "../../../shared/api";
import { baseSummary, competitionSettings } from "./admin/admin-test-fixtures";
import { AdminView } from "./AdminView";

const mocks = vi.hoisted(() => ({
  getOpsNeonUsage: vi.fn(),
  getOpsAdminSummary: vi.fn(),
  updateOpsCompetitionSetting: vi.fn(),
  sendAdminTestAlert: vi.fn(),
}));

vi.mock("../../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../../shared/api")>("../../../shared/api");
  return { ...actual, ...mocks };
});

function renderAdmin(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <AdminView token="token" />
      </QueryClientProvider>,
    ),
  };
}

async function settle(ms = 1) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function openActivity() {
  fireEvent.click(screen.getByRole("tab", { name: "Activity & tools" }));
  await settle();
}

describe("AdminView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-04T16:00:00Z"));
    vi.resetAllMocks();
    mocks.getOpsAdminSummary.mockImplementation(async (_token, window) => ({
      ...structuredClone(baseSummary),
      overview: { ...baseSummary.overview, window, last_updated_at: new Date().toISOString() },
    }));
    mocks.getOpsNeonUsage.mockResolvedValue({
      available: true,
      dashboard_url: "https://example.com/neon",
      consumption_period_end: "2026-10-01T00:00:00Z",
      cpu_used_sec: 7200,
      active_time_sec: 3600,
      avg_cu_while_active: 2,
    });
  });

  afterEach(() => {
    cleanup();
    focusManager.setFocused(undefined);
    onlineManager.setOnline(true);
    vi.useRealTimers();
  });

  it("shows reported schedules with local countdowns and no polling", async () => {
    const reportedAt = new Date(Date.now() - 60_000).toISOString();
    mocks.getOpsAdminSummary.mockResolvedValue({
      ...baseSummary,
      schedule: {
        reported_at: reportedAt,
        next_catalog_at: new Date(Date.now() + 43_200_000).toISOString(),
        jobs: [
          {
            competition: "WNBA",
            job_type: "catalog_sync",
            next_run_at: new Date(Date.now() + 7_200_000).toISOString(),
            last_success_at: reportedAt,
            state: "scheduled",
          },
          {
            competition: "WNBA",
            job_type: "live_sync",
            next_run_at: new Date(Date.now() + 3_000).toISOString(),
            last_success_at: reportedAt,
            state: "live",
          },
          {
            competition: "MLB",
            job_type: "catalog_sync",
            next_run_at: new Date(Date.now() + 90_000).toISOString(),
            last_success_at: null,
            state: "retry_scheduled",
          },
          {
            competition: "MLB",
            job_type: "live_sync",
            next_run_at: new Date(Date.now() + 3_600_000).toISOString(),
            last_success_at: null,
            state: "waiting_for_start",
          },
        ],
      },
    });
    const interval = vi.spyOn(globalThis, "setInterval");
    const clear = vi.spyOn(globalThis, "clearInterval");
    const view = renderAdmin();
    await settle();
    expect(interval).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("tab", { name: "Leagues" }));
    const panel = within(screen.getByRole("tabpanel", { name: "Leagues" }));
    expect(panel.queryByText(/^Catalog sync/)).toBeNull();
    const liveRow = within(panel.getByRole("listitem", { name: "WNBA" }));
    expect(liveRow.getByText("In 3s")).toBeInTheDocument();
    expect(liveRow.getByText("Every 2m")).toBeInTheDocument();
    expect(panel.queryByText("Last success")).toBeNull();
    await settle(1000);
    expect(liveRow.getByText("In 2s")).toBeInTheDocument();
    await settle(2000);
    expect(liveRow.getByText("Scheduled time passed — reload for status")).toBeInTheDocument();
    await settle(10 * 60_000);
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsNeonUsage).not.toHaveBeenCalled();

    const timer = interval.mock.results[interval.mock.results.length - 1]?.value;
    const visibility = vi.spyOn(document, "visibilityState", "get");
    visibility.mockReturnValue("hidden");
    fireEvent(document, new Event("visibilitychange"));
    expect(clear).toHaveBeenCalledWith(timer);
    const calls = interval.mock.calls.length;
    await settle(60_000);
    expect(interval).toHaveBeenCalledTimes(calls);
    visibility.mockReturnValue("visible");
    fireEvent(document, new Event("visibilitychange"));
    expect(interval).toHaveBeenCalledTimes(calls + 1);
    const visibleTimer = interval.mock.results[interval.mock.results.length - 1]?.value;
    fireEvent.click(screen.getByRole("tab", { name: "Activity & tools" }));
    expect(clear).toHaveBeenCalledWith(visibleTimer);
    fireEvent.click(screen.getByRole("tab", { name: "Leagues" }));
    const remountedTimer = interval.mock.results[interval.mock.results.length - 1]?.value;
    view.unmount();
    expect(clear).toHaveBeenCalledWith(remountedTimer);
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
    vi.restoreAllMocks();
  });

  it("does not surface shared catalog work in the league table", async () => {
    mocks.getOpsAdminSummary.mockResolvedValue({
      ...baseSummary,
      schedule: {
        reported_at: new Date().toISOString(),
        next_catalog_at: new Date(Date.now() + 2000).toISOString(),
        jobs: [
          {
            competition: "WNBA",
            job_type: "catalog_sync",
            state: "queued",
            next_run_at: new Date().toISOString(),
            last_success_at: null,
          },
          {
            competition: "WNBA",
            job_type: "live_sync",
            state: "live",
            next_run_at: new Date(Date.now() + 3600000).toISOString(),
            last_success_at: null,
          },
        ],
      },
    });
    renderAdmin();
    await settle();
    fireEvent.click(screen.getByRole("tab", { name: "Leagues" }));
    expect(screen.queryByText(/^Catalog sync/)).toBeNull();
    expect(screen.queryByText("Catalog pending")).toBeNull();
    expect(
      within(screen.getByRole("listitem", { name: "WNBA" })).getByText("In 1h 0m"),
    ).toBeInTheDocument();
    await settle(3000);
    expect(screen.queryByText("Catalog pending")).toBeNull();
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsNeonUsage).not.toHaveBeenCalled();
  });

  it("distinguishes discovery and disabled leagues without a manual refresh control", async () => {
    const summary = {
      ...baseSummary,
      competition_settings: [
        ...competitionSettings,
        { ...competitionSettings[0], competition: "NBA", label: "NBA", is_enabled: false },
        { ...competitionSettings[0], competition: "NFL", label: "NFL", is_enabled: false },
      ],
      schedule: {
        reported_at: new Date().toISOString(),
        next_catalog_at: new Date(Date.now() + 43_200_000).toISOString(),
        jobs: [
          {
            competition: "WNBA",
            job_type: "catalog_sync",
            next_run_at: new Date(Date.now() + 60_000).toISOString(),
            state: "awaiting_first_result",
            last_success_at: null,
          },
          {
            competition: "WNBA",
            job_type: "live_sync",
            next_run_at: null,
            state: "no_upcoming",
            last_success_at: null,
          },
          {
            competition: "NBA",
            job_type: "live_sync",
            next_run_at: new Date(Date.now() + 60_000).toISOString(),
            state: "live",
            last_success_at: null,
          },
        ],
      },
    };
    mocks.getOpsAdminSummary.mockResolvedValue(summary);
    renderAdmin();
    await settle();
    fireEvent.click(screen.getByRole("tab", { name: "Leagues" }));
    const wnbaRow = within(screen.getByRole("listitem", { name: "WNBA" }));
    expect(wnbaRow.getByText("No upcoming games")).toBeInTheDocument();
    expect(wnbaRow.getByText("Rechecked after catalog")).toBeInTheDocument();
    expect(screen.getAllByText("Awaiting worker discovery")).toHaveLength(3);
    expect(screen.getByRole("switch", { name: "NBA league enabled" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByText("Worker confirmation pending")).toBeVisible();
    expect(screen.getByRole("switch", { name: "NFL league enabled" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.queryByRole("button", { name: "Refresh" })).toBeNull();
  });

  it("refreshes the summary on reopening and loads database usage on demand", async () => {
    const first = renderAdmin();
    expect(screen.getByText("Loading admin data…")).toBeInTheDocument();
    await settle();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Leagues",
      "Activity & tools",
    ]);
    expect(screen.getByRole("tab", { name: "Leagues" })).toHaveAttribute("aria-selected", "true");
    expect(mocks.getOpsNeonUsage).not.toHaveBeenCalled();
    await openActivity();
    expect(screen.getByRole("region", { name: "Test alerts" })).toBeVisible();
    expect(screen.getByText("Alerts created").closest(".admin-activity-total")).toHaveTextContent(
      "3",
    );
    const email = screen.getByRole("row", { name: "Email 2 3 1" });
    expect(within(email).getByRole("cell", { name: "1" })).toHaveClass("is-danger");
    expect(screen.getByText("2.00 CUh")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Neon" })).toHaveAttribute(
      "href",
      "https://example.com/neon",
    );
    first.unmount();
    renderAdmin(first.client);
    await settle();
    await openActivity();
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(2);
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
  });

  it.each(["Leagues", "Activity & tools"])(
    "does not poll or refetch on foreground and network recovery in %s",
    async (tab) => {
      renderAdmin();
      await settle();
      fireEvent.click(screen.getByRole("tab", { name: tab }));
      await settle(10 * 60_000);
      act(() => {
        focusManager.setFocused(false);
        onlineManager.setOnline(false);
      });
      fireEvent(document, new Event("visibilitychange"));
      fireEvent(window, new Event("pageshow"));
      act(() => {
        focusManager.setFocused(true);
        onlineManager.setOnline(true);
      });
      await settle();
      expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
      expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(tab === "Leagues" ? 0 : 1);
    },
  );

  it("reuses tab data without refetching when tabs change", async () => {
    renderAdmin();
    await settle();
    expect(screen.queryByRole("combobox", { name: "Activity window" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Refresh" })).toBeNull();
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsNeonUsage).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Leagues" }), { key: "ArrowRight" });
    await settle(20);
    expect(screen.getByRole("tab", { name: "Activity & tools" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("combobox", { name: "Activity window" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Send test alert" })).toBeVisible();
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(screen.getByRole("tab", { name: "Activity & tools" }), { key: "ArrowRight" });
    await settle(20);
    expect(screen.getByRole("tab", { name: "Leagues" })).toHaveAttribute("aria-selected", "true");
    await openActivity();
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
  });

  it("preserves league scroll, form selections and pending delivery across tabs", async () => {
    renderAdmin();
    await settle();
    fireEvent.click(screen.getByRole("tab", { name: "Leagues" }));
    const list = screen.getByLabelText("League list");
    list.scrollTop = 120;
    fireEvent.click(screen.getByRole("tab", { name: "Activity & tools" }));
    fireEvent.change(screen.getByRole("combobox", { name: "League" }), {
      target: { value: "MLB" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Alert type" }), {
      target: { value: "inning_start" },
    });
    let finish!: (value: unknown) => void;
    mocks.sendAdminTestAlert.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Send test alert" }));
    fireEvent.click(screen.getByRole("tab", { name: "Leagues" }));
    expect(list.scrollTop).toBe(120);
    fireEvent.click(screen.getByRole("tab", { name: "Activity & tools" }));
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "League" })).toHaveValue("MLB");
    expect(screen.getByRole("combobox", { name: "Alert type" })).toHaveValue("inning_start");
    finish({ deliveries: [{ channel: "email", status: "sent" }] });
    await settle();
    expect(screen.getByText("Inning start test for MLB: email sent.")).toBeVisible();
    expect(mocks.sendAdminTestAlert).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Inning start test for MLB: email sent.")).toBeVisible();
  });

  it("fetches each selected window including previously cached windows", async () => {
    renderAdmin();
    await settle();
    await openActivity();
    let finish!: (value: OpsAdminSummaryResponse) => void;
    mocks.getOpsAdminSummary.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    fireEvent.change(screen.getByRole("combobox", { name: "Activity window" }), {
      target: { value: "7d" },
    });
    await settle();
    expect(screen.getByText("Alerts created").closest(".admin-activity-total")).toHaveTextContent(
      "3",
    );
    finish({
      ...baseSummary,
      overview: { ...baseSummary.overview, window: "7d", total_alerts_created: 9 },
    });
    await settle();
    expect(screen.getByText("Alerts created").closest(".admin-activity-total")).toHaveTextContent(
      "9",
    );
    fireEvent.change(screen.getByRole("combobox", { name: "Activity window" }), {
      target: { value: "24h" },
    });
    await settle();
    expect(mocks.getOpsAdminSummary.mock.calls.map((call) => call[1])).toEqual([
      "24h",
      "7d",
      "24h",
    ]);
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
  });

  it("shows initial errors without periodic retries or manual refresh", async () => {
    mocks.getOpsAdminSummary.mockRejectedValueOnce(new Error("Admin unavailable"));
    mocks.getOpsNeonUsage.mockRejectedValueOnce(new Error("Neon unavailable"));
    renderAdmin();
    await openActivity();
    expect(screen.getByText("Admin unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh" })).toBeNull();
    await settle(10 * 60_000);
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(1);
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
  });

  it("preserves the bounded retry and resumes a requested offline load", async () => {
    onlineManager.setOnline(false);
    mocks.getOpsAdminSummary.mockRejectedValueOnce(new Error("Temporary failure"));
    renderAdmin(new QueryClient({ defaultOptions: { queries: { retry: 1, retryDelay: 100 } } }));
    await openActivity();
    expect(mocks.getOpsAdminSummary).not.toHaveBeenCalled();
    act(() => onlineManager.setOnline(true));
    await settle(200);
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(2);
    expect(mocks.getOpsNeonUsage).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Alerts created")).toBeInTheDocument();
  });

  it("refreshes competition settings after a successful toggle", async () => {
    renderAdmin();
    await settle();
    fireEvent.click(screen.getByRole("tab", { name: "Leagues" }));
    mocks.updateOpsCompetitionSetting.mockResolvedValue({
      ...competitionSettings[0],
      is_enabled: false,
    });
    mocks.getOpsAdminSummary.mockResolvedValueOnce({
      ...baseSummary,
      schedule: null,
      competition_settings: [
        { ...competitionSettings[0], is_enabled: false },
        competitionSettings[1],
      ],
    });
    fireEvent.click(screen.getByRole("switch", { name: "WNBA league enabled" }));
    await settle();
    expect(screen.getByRole("switch", { name: "WNBA league enabled" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(mocks.getOpsAdminSummary).toHaveBeenCalledTimes(2);
    expect(mocks.getOpsNeonUsage).not.toHaveBeenCalled();
  });
});
