import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type CompetitionSetting, type ScheduleSnapshot } from "../../../../shared/api";
import { basketballCompetition as item, baseballCompetition } from "./admin-test-fixtures";
import { AdminLeaguesPanel } from "./AdminLeaguesPanel";

const updateOpsCompetitionSettingMock = vi.hoisted(() => vi.fn());

vi.mock("../../../../shared/api", async () => {
  const actual =
    await vi.importActual<typeof import("../../../../shared/api")>("../../../../shared/api");
  return { ...actual, updateOpsCompetitionSetting: updateOpsCompetitionSettingMock };
});

function makeSchedule(
  jobs: ScheduleSnapshot["jobs"] = [],
  nextCatalogAt = new Date(Date.now() + 60_000).toISOString(),
): ScheduleSnapshot {
  return {
    reported_at: new Date().toISOString(),
    next_catalog_at: nextCatalogAt,
    jobs,
  };
}

function renderPanel(
  items: CompetitionSetting[] = [item],
  schedule: ScheduleSnapshot | null = null,
) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  function panel(nextItems: CompetitionSetting[], nextSchedule: ScheduleSnapshot | null) {
    return (
      <QueryClientProvider client={client}>
        <AdminLeaguesPanel token="token" items={nextItems} schedule={nextSchedule} active />
      </QueryClientProvider>
    );
  }
  const view = render(panel(items, schedule));
  return {
    invalidate,
    rerender: (nextItems: CompetitionSetting[], nextSchedule: ScheduleSnapshot | null = schedule) =>
      view.rerender(panel(nextItems, nextSchedule)),
  };
}

describe("AdminLeaguesPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateOpsCompetitionSettingMock.mockResolvedValue({ ...item, is_enabled: false });
  });

  it("updates a competition and invalidates the affected views", async () => {
    const { invalidate } = renderPanel();
    const toggle = screen.getByRole("switch", { name: "WNBA league enabled" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    fireEvent.click(toggle);

    await waitFor(() =>
      expect(updateOpsCompetitionSettingMock).toHaveBeenCalledWith("token", "WNBA", false),
    );
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(4));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-page", "token"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["games"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["teams"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["competitions"] });
  });

  it("shows saving and error states without changing the confirmed switch state", async () => {
    let rejectUpdate: ((error: Error) => void) | undefined;
    updateOpsCompetitionSettingMock.mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectUpdate = reject;
        }),
    );
    renderPanel();

    const toggle = screen.getByRole("switch", { name: "WNBA league enabled" });
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toBeDisabled());
    expect(toggle).toHaveTextContent("Saving…");
    expect(toggle).toHaveAttribute("aria-checked", "true");

    rejectUpdate?.(new Error("Competition update failed"));
    expect(await screen.findByText("Competition update failed")).toBeInTheDocument();
    expect(toggle).toBeEnabled();
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("renders compact rows with enabled leagues first and no global status", () => {
    renderPanel([{ ...item, is_enabled: false }, baseballCompetition]);
    const list = within(screen.getByLabelText("League list"));
    expect(list.getAllByRole("listitem").map((row) => row.getAttribute("aria-label"))).toEqual([
      "MLB",
      "WNBA",
    ]);

    const mlb = within(list.getByRole("listitem", { name: "MLB" }));
    expect(mlb.getByText("Live sync")).toBeInTheDocument();
    expect(mlb.getAllByText("Schedule unavailable")).toHaveLength(2);
    expect(mlb.getByText("Every 5m")).toBeInTheDocument();
    expect(mlb.getByRole("switch", { name: "MLB league enabled" })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    const wnba = within(list.getByRole("listitem", { name: "WNBA" }));
    expect(wnba.getByText("Not scheduled")).toBeInTheDocument();
    expect(wnba.getByText("Every 2m when enabled")).toBeInTheDocument();
    expect(wnba.getByText("Odds disabled")).toBeInTheDocument();
    expect(wnba.getByRole("switch", { name: "WNBA league enabled" })).toHaveAttribute(
      "aria-checked",
      "false",
    );

    expect(screen.queryByText(/^Catalog sync/)).toBeNull();
    expect(screen.queryByText(/^Odds API:/)).toBeNull();
  });

  it("handles an empty league list and renders rows when data arrives", () => {
    const { rerender } = renderPanel([]);
    expect(screen.getByText("No leagues available.")).toBeVisible();
    expect(screen.queryByRole("switch")).toBeNull();
    rerender([baseballCompetition]);
    expect(screen.getByRole("switch", { name: "MLB league enabled" })).toBeVisible();
  });

  it("keeps pending actions and errors associated with the affected league", async () => {
    let rejectUpdate!: (error: Error) => void;
    updateOpsCompetitionSettingMock.mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectUpdate = reject;
        }),
    );
    renderPanel([item, baseballCompetition]);
    const wnbaToggle = screen.getByRole("switch", { name: "WNBA league enabled" });
    const mlbToggle = screen.getByRole("switch", { name: "MLB league enabled" });
    fireEvent.click(wnbaToggle);
    await waitFor(() => expect(wnbaToggle).toHaveTextContent("Saving…"));
    expect(mlbToggle).toBeDisabled();
    expect(mlbToggle).toHaveTextContent("On");
    rejectUpdate(new Error("WNBA update failed"));
    await waitFor(() => expect(mlbToggle).toBeEnabled());
    expect(within(screen.getByRole("listitem", { name: "MLB" })).queryByRole("alert")).toBeNull();
    expect(
      within(screen.getByRole("listitem", { name: "WNBA" })).getByRole("alert"),
    ).toHaveTextContent("WNBA update failed");
  });

  it.each([
    ["awaiting_first_result", "Awaiting catalog", "Odds run follows catalog"],
    ["queued", "Queued", "Waiting to run"],
    ["no_upcoming", "No pending odds", "Rechecked after catalog"],
    ["budget_limited", "Budget limited", "Retry in"],
    ["retry_scheduled", "Retry in", "Previous attempt failed"],
    ["scheduled", "In 1m", "Scheduled odds sync"],
  ] as const)("renders the %s odds state", (state, value, detail) => {
    const nextRun = new Date(Date.now() + 60_000).toISOString();
    renderPanel(
      [item],
      makeSchedule([
        {
          competition: item.competition,
          job_type: "live_sync",
          next_run_at: nextRun,
          last_success_at: null,
          state: "waiting_for_start",
        },
        {
          competition: item.competition,
          job_type: "odds_sync",
          next_run_at: nextRun,
          last_success_at: null,
          state,
        },
      ]),
    );

    const row = within(screen.getByRole("listitem", { name: "WNBA" }));
    const odds = within(row.getByText("Odds").closest("dl")!);
    expect(odds.getByText((content) => content.startsWith(value))).toBeInTheDocument();
    expect(odds.getByText((content) => content.startsWith(detail))).toBeInTheDocument();
  });

  it("renders a dormant live job without a countdown", () => {
    renderPanel(
      [item],
      makeSchedule([
        {
          competition: item.competition,
          job_type: "live_sync",
          next_run_at: null,
          last_success_at: new Date().toISOString(),
          state: "no_upcoming",
        },
        {
          competition: item.competition,
          job_type: "odds_sync",
          next_run_at: null,
          last_success_at: new Date().toISOString(),
          state: "no_upcoming",
        },
      ]),
    );

    const row = within(screen.getByRole("listitem", { name: "WNBA" }));
    const live = within(row.getByText("Live sync").closest("dl")!);
    expect(live.getByText("No upcoming games")).toBeInTheDocument();
    expect(live.getByText("Rechecked after catalog")).toBeInTheDocument();
    expect(live.queryByText(/^In /)).toBeNull();
    expect(live.queryByText("Scheduled time passed — reload for status")).toBeNull();
  });

  it("handles missing deadlines for states that require one", () => {
    renderPanel(
      [item],
      makeSchedule([
        {
          competition: item.competition,
          job_type: "live_sync",
          next_run_at: null,
          last_success_at: null,
          state: "waiting_for_start",
        },
        {
          competition: item.competition,
          job_type: "odds_sync",
          next_run_at: null,
          last_success_at: null,
          state: "scheduled",
        },
      ]),
    );

    const row = within(screen.getByRole("listitem", { name: "WNBA" }));
    expect(row.getAllByText("Schedule unavailable")).toHaveLength(2);
    expect(row.getAllByText("Reload for worker status")).toHaveLength(2);
  });

  it("shows discovery, retry, passed, and stale disabled schedule states", () => {
    const retryAt = new Date(Date.now() + 60_000).toISOString();
    const passedAt = new Date(Date.now() - 1_000).toISOString();
    const nba = { ...item, competition: "NBA" as const, label: "NBA" };
    const nfl = { ...item, competition: "NFL" as const, label: "NFL", is_enabled: false };
    renderPanel(
      [item, nba, nfl],
      makeSchedule([
        {
          competition: item.competition,
          job_type: "live_sync",
          next_run_at: retryAt,
          last_success_at: null,
          state: "retry_scheduled",
        },
        {
          competition: item.competition,
          job_type: "odds_sync",
          next_run_at: passedAt,
          last_success_at: null,
          state: "scheduled",
        },
        {
          competition: nfl.competition,
          job_type: "live_sync",
          next_run_at: retryAt,
          last_success_at: null,
          state: "scheduled",
        },
      ]),
    );

    const wnba = within(screen.getByRole("listitem", { name: "WNBA" }));
    expect(wnba.getByText(/^Retry in/)).toHaveClass("is-danger");
    expect(wnba.getByText("Scheduled time passed — reload for status")).toBeInTheDocument();
    const nbaRow = within(screen.getByRole("listitem", { name: "NBA" }));
    expect(nbaRow.getAllByText("Awaiting worker discovery")).toHaveLength(2);
    const nflRow = within(screen.getByRole("listitem", { name: "NFL" }));
    expect(nflRow.getByText("Worker confirmation pending")).toBeInTheDocument();
    expect(nflRow.getByText("Odds disabled")).toBeInTheDocument();
  });
});
