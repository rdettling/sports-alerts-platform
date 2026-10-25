import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AlertsView } from "./AlertsView";

const apiMocks = vi.hoisted(() => ({
  listAlertHistory: vi.fn(),
  listAlertPreferences: vi.fn(),
  updateAlertPreference: vi.fn(),
}));

vi.mock("../../shared/api", () => apiMocks);

vi.mock("./AlertDeliverySettings", () => ({
  AlertDeliverySettings: () => <section aria-label="Delivery settings">Delivery settings</section>,
}));

const basketballPreferences = [
  {
    competition: "NBA",
    alert_type: "game_start",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
  {
    competition: "NBA",
    alert_type: "close_game_late",
    is_enabled: true,
    close_game_margin_threshold: 5,
    close_game_time_threshold_seconds: 300,
    periods: null,
  },
  {
    competition: "NBA",
    alert_type: "overtime_start",
    is_enabled: false,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
  {
    competition: "NBA",
    alert_type: "final_result",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
];

const baseballPreferences = [
  {
    competition: "MLB",
    alert_type: "game_start",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
  {
    competition: "MLB",
    alert_type: "inning_start",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: [7],
  },
];

const footballPreferences = [
  {
    competition: "NFL",
    alert_type: "score_changed",
    is_enabled: false,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
  {
    competition: "NFL",
    alert_type: "lead_change",
    is_enabled: false,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
];

const hockeyPreferences = [
  {
    competition: "NHL",
    alert_type: "game_start",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
  {
    competition: "NHL",
    alert_type: "close_game_late",
    is_enabled: true,
    close_game_margin_threshold: 1,
    close_game_time_threshold_seconds: 300,
    periods: null,
  },
  {
    competition: "NHL",
    alert_type: "score_changed",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    periods: null,
  },
];

const preferenceGroups = [
  { competition: "NBA", label: "NBA", preferences: basketballPreferences },
  { competition: "NFL", label: "NFL", preferences: footballPreferences },
  { competition: "MLB", label: "MLB", preferences: baseballPreferences },
  { competition: "NHL", label: "NHL", preferences: hockeyPreferences },
];

const historyItems = [
  {
    id: 1,
    game_id: 11,
    alert_type: "game_start",
    triggered_at: "2026-08-13T16:30:00-07:00",
    game_external_id: "game-1",
    home_team_abbreviation: "LV",
    away_team_abbreviation: "NY",
    deliveries: [
      { channel: "email", status: "sent", attempted_at: "2026-08-13T16:30:02-07:00" },
      { channel: "push", status: "pending", attempted_at: null },
    ],
  },
  {
    id: 2,
    game_id: 12,
    alert_type: "final_result",
    triggered_at: "2026-08-13T15:00:00-07:00",
    game_external_id: "game-2",
    home_team_abbreviation: "SEA",
    away_team_abbreviation: "ATL",
    deliveries: [],
  },
  {
    id: 4,
    game_id: 14,
    alert_type: "lead_change",
    triggered_at: "2026-08-13T14:00:00-07:00",
    game_external_id: "game-4",
    home_team_abbreviation: "BUF",
    away_team_abbreviation: "KC",
    deliveries: [{ channel: "push", status: "sent", attempted_at: "2026-08-13T14:00:02-07:00" }],
  },
  {
    id: 3,
    game_id: 13,
    alert_type: "inning_start",
    triggered_at: "2026-08-12T20:00:00-07:00",
    game_external_id: "game-3",
    home_team_abbreviation: "LAD",
    away_team_abbreviation: "SF",
    deliveries: [{ channel: "email", status: "failed", attempted_at: "2026-08-12T20:00:02-07:00" }],
  },
];

describe("AlertsView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-08-13T18:00:00-07:00").getTime());
    apiMocks.listAlertPreferences.mockResolvedValue(preferenceGroups);
    apiMocks.listAlertHistory.mockResolvedValue({ items: historyItems });
    apiMocks.updateAlertPreference.mockImplementation((_token, competition, alertType, payload) =>
      Promise.resolve({ competition, alert_type: alertType, ...payload }),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads the first active league and groups recent history by local day", async () => {
    render(<AlertsView token="token" />);
    expect(screen.getByText("Loading alerts...")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Alert Rules" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "NBA" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Close game late")).toBeInTheDocument();
    expect(screen.queryByText("Score update")).toBeNull();
    expect(screen.getByRole("switch", { name: "Overtime start alerts" })).toHaveAttribute(
      "aria-checked",
      "false",
    );

    expect(screen.getByText("Last 7 days · 4 events")).toBeInTheDocument();
    const today = screen.getByRole("region", { name: "Today" });
    expect(within(today).getAllByRole("listitem")[0]).toHaveTextContent("NY @ LV");
    expect(within(today).getAllByRole("listitem")[1]).toHaveTextContent("ATL @ SEA");
    expect(within(today).getByText("Email sent")).toBeInTheDocument();
    expect(within(today).getByText("Push pending")).toBeInTheDocument();
    expect(within(today).getByText("Email sent")).toHaveClass("status-sent");
    expect(within(today).getByText("Push pending")).toHaveClass("status-pending");
    expect(within(today).getByText("—")).toBeInTheDocument();
    expect(within(today).getByText("Lead change")).toBeInTheDocument();
    const yesterday = screen.getByRole("region", { name: "Yesterday" });
    expect(yesterday).toHaveTextContent("Email failed");
    expect(within(yesterday).getByText("Email failed")).toHaveClass("status-failed");
  });

  it("switches leagues and shows that league's rules", async () => {
    render(<AlertsView token="token" />);
    fireEvent.click(await screen.findByRole("button", { name: "MLB" }));

    expect(screen.getByRole("button", { name: "MLB" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("switch", { name: "Inning start alerts" })).toBeInTheDocument();
    expect(screen.queryByText("Close game late")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "NFL" }));
    expect(screen.getByRole("switch", { name: "Score update alerts" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByRole("switch", { name: "Lead change alerts" })).toHaveAttribute(
      "aria-checked",
      "false",
    );

    fireEvent.click(screen.getByRole("button", { name: "NHL" }));
    expect(screen.getByRole("switch", { name: "Score update alerts" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByLabelText("Margin")).toHaveValue("1");
    expect(screen.getByLabelText("Minutes")).toHaveValue("5");
    expect(screen.queryByRole("switch", { name: "Lead change alerts" })).toBeNull();
  });

  it.each([
    ["NBA", "basketball", "quarter_start", "Quarter starts"],
    ["NHL", "hockey", "period_start", "Period starts"],
    ["NCAAB", "basketball", "second_half_start", "Second half start"],
  ])(
    "enables %s start alerts through the existing preferences",
    async (competition, sport, alertType, label) => {
      const preference = {
        competition,
        alert_type: alertType,
        is_enabled: false,
        close_game_margin_threshold: null,
        close_game_time_threshold_seconds: null,
        periods:
          alertType === "quarter_start" ? [2, 3, 4] : alertType === "period_start" ? [2, 3] : null,
      };
      apiMocks.listAlertPreferences.mockResolvedValue([
        { competition, sport, label: competition, preferences: [preference] },
      ]);
      apiMocks.updateAlertPreference.mockResolvedValue({ ...preference, is_enabled: true });
      render(<AlertsView token="token" />);
      const toggle = await screen.findByRole("switch", { name: `${label} alerts` });
      expect(toggle).toHaveAttribute("aria-checked", "false");
      fireEvent.click(toggle);
      await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
      expect(apiMocks.updateAlertPreference).toHaveBeenCalledWith("token", competition, alertType, {
        is_enabled: true,
        close_game_margin_threshold: null,
        close_game_time_threshold_seconds: null,
        periods:
          alertType === "quarter_start" ? [2, 3, 4] : alertType === "period_start" ? [2, 3] : null,
      });
    },
  );

  it("saves a combination of periods and preserves it when switched off", async () => {
    const preference = {
      competition: "NBA",
      alert_type: "quarter_start",
      is_enabled: true,
      close_game_margin_threshold: null,
      close_game_time_threshold_seconds: null,
      periods: [2, 3, 4],
    };
    apiMocks.listAlertPreferences.mockResolvedValue([
      { competition: "NBA", label: "NBA", preferences: [preference] },
    ]);
    render(<AlertsView token="token" />);
    const q3 = await screen.findByRole("checkbox", { name: "Q3" });
    fireEvent.click(q3);
    await waitFor(() => expect(q3).not.toBeChecked());
    expect(screen.getByRole("checkbox", { name: "Q2" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Q4" })).toBeChecked();
    expect(apiMocks.updateAlertPreference).toHaveBeenLastCalledWith(
      "token",
      "NBA",
      "quarter_start",
      expect.objectContaining({ is_enabled: true, periods: [2, 4] }),
    );
    fireEvent.click(screen.getByRole("switch", { name: "Quarter starts alerts" }));
    await waitFor(() => expect(q3).toBeDisabled());
    expect(apiMocks.updateAlertPreference).toHaveBeenLastCalledWith(
      "token",
      "NBA",
      "quarter_start",
      expect.objectContaining({ is_enabled: false, periods: [2, 4] }),
    );
  });

  it("saves any combination of hockey period starts", async () => {
    const preference = {
      competition: "NHL",
      alert_type: "period_start",
      is_enabled: true,
      close_game_margin_threshold: null,
      close_game_time_threshold_seconds: null,
      periods: [2, 3],
    };
    apiMocks.listAlertPreferences.mockResolvedValue([
      { competition: "NHL", label: "NHL", preferences: [preference] },
    ]);
    render(<AlertsView token="token" />);
    const p2 = await screen.findByRole("checkbox", { name: "P2" });
    const p3 = screen.getByRole("checkbox", { name: "P3" });
    expect(screen.queryByRole("checkbox", { name: "P4" })).toBeNull();
    fireEvent.click(p2);
    await waitFor(() => expect(p2).not.toBeChecked());
    expect(p3).toBeChecked();
    expect(apiMocks.updateAlertPreference).toHaveBeenLastCalledWith(
      "token",
      "NHL",
      "period_start",
      expect.objectContaining({ periods: [3] }),
    );
    fireEvent.click(p2);
    await waitFor(() => expect(p2).toBeChecked());
    fireEvent.click(p3);
    await waitFor(() => expect(p3).not.toBeChecked());
    expect(apiMocks.updateAlertPreference).toHaveBeenLastCalledWith(
      "token",
      "NHL",
      "period_start",
      expect.objectContaining({ periods: [2] }),
    );
  });

  it("saves a combination of MLB innings inline", async () => {
    render(<AlertsView token="token" />);
    fireEvent.click(await screen.findByRole("button", { name: "MLB" }));
    expect(screen.getByRole("checkbox", { name: "Inning 7" })).toBeChecked();
    expect(screen.getAllByRole("checkbox")).toHaveLength(9);
    const inning2 = screen.getByRole("checkbox", { name: "Inning 2" });
    fireEvent.click(inning2);
    await waitFor(() => expect(inning2).toBeChecked());
    const inning9 = screen.getByRole("checkbox", { name: "Inning 9" });
    fireEvent.click(inning9);
    await waitFor(() => expect(inning9).toBeChecked());
    expect(apiMocks.updateAlertPreference).toHaveBeenLastCalledWith(
      "token",
      "MLB",
      "inning_start",
      expect.objectContaining({ periods: [2, 7, 9] }),
    );
  });

  it("updates a switch and local state without refetching alert data", async () => {
    let finishUpdate: (() => void) | undefined;
    apiMocks.updateAlertPreference.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishUpdate = () => resolve({ ...basketballPreferences[0], is_enabled: false });
        }),
    );
    render(<AlertsView token="token" />);

    const toggle = await screen.findByRole("switch", { name: "Game start alerts" });
    fireEvent.click(toggle);
    expect(toggle).toBeDisabled();
    await waitFor(() =>
      expect(apiMocks.updateAlertPreference).toHaveBeenCalledWith("token", "NBA", "game_start", {
        is_enabled: false,
        close_game_margin_threshold: null,
        close_game_time_threshold_seconds: null,
        periods: null,
      }),
    );

    finishUpdate?.();
    await waitFor(() => expect(toggle).not.toBeDisabled());
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(apiMocks.listAlertPreferences).toHaveBeenCalledTimes(1);
  });

  it("converts threshold minutes to seconds and reports update errors", async () => {
    render(<AlertsView token="token" />);
    const minutes = await screen.findByRole("combobox", { name: "Minutes" });

    fireEvent.change(minutes, { target: { value: "10" } });
    await waitFor(() =>
      expect(apiMocks.updateAlertPreference).toHaveBeenCalledWith(
        "token",
        "NBA",
        "close_game_late",
        {
          is_enabled: true,
          close_game_margin_threshold: 5,
          close_game_time_threshold_seconds: 600,
          periods: null,
        },
      ),
    );

    apiMocks.updateAlertPreference.mockRejectedValueOnce(new Error("Could not save rule"));
    fireEvent.click(screen.getByRole("switch", { name: "Final result alerts" }));
    expect(await screen.findByText("Could not save rule")).toBeInTheDocument();
  });

  it("shows load errors and empty rule and history states", async () => {
    apiMocks.listAlertPreferences.mockRejectedValueOnce(new Error("Alerts unavailable"));
    const failed = render(<AlertsView token="token" />);
    expect(await screen.findByText("Alerts unavailable")).toBeInTheDocument();
    failed.unmount();

    apiMocks.listAlertPreferences.mockResolvedValue([]);
    apiMocks.listAlertHistory.mockResolvedValue({ items: [] });
    render(<AlertsView token="token" />);
    expect(await screen.findByText("No rules for this league.")).toBeInTheDocument();
    expect(screen.getByText("No alert history yet.")).toBeInTheDocument();
    expect(screen.getByText("Last 7 days · 0 events")).toBeInTheDocument();
  });

  it("refreshes every two minutes and clears polling on unmount", async () => {
    let poll: (() => void) | undefined;
    const intervalSpy = vi.spyOn(window, "setInterval").mockImplementation((callback, delay) => {
      expect(delay).toBe(120_000);
      poll = callback as () => void;
      return 42;
    });
    const clearSpy = vi.spyOn(window, "clearInterval").mockImplementation(() => undefined);
    const view = render(<AlertsView token="token" />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByRole("heading", { name: "Alert Rules" })).toBeInTheDocument();
    expect(apiMocks.listAlertPreferences).toHaveBeenCalledTimes(1);

    await act(async () => {
      poll?.();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(apiMocks.listAlertPreferences).toHaveBeenCalledTimes(2);

    view.unmount();
    expect(intervalSpy).toHaveBeenCalledTimes(1);
    expect(clearSpy).toHaveBeenCalledWith(42);
  });
});

describe("league selection", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });
  it("keeps league settings independent while history stays global", async () => {
    const groups = ["NBA", "WNBA", "NCAAB"].map((competition) => ({
      competition,
      label: competition === "NCAAB" ? "CBB" : competition,
      preferences: basketballPreferences.map((preference) => ({ ...preference, competition })),
    }));
    apiMocks.listAlertPreferences.mockResolvedValue(groups);
    apiMocks.listAlertHistory.mockResolvedValue({ items: historyItems });
    apiMocks.updateAlertPreference.mockImplementation((_token, competition, alert_type, payload) =>
      Promise.resolve({ competition, alert_type, ...payload }),
    );
    render(<AlertsView token="token" />);
    fireEvent.click(await screen.findByRole("button", { name: "CBB" }));
    fireEvent.click(screen.getByRole("switch", { name: "Game start alerts" }));
    await waitFor(() =>
      expect(screen.getByRole("switch", { name: "Game start alerts" })).toHaveAttribute(
        "aria-checked",
        "false",
      ),
    );
    expect(apiMocks.updateAlertPreference).toHaveBeenCalledWith(
      "token",
      "NCAAB",
      "game_start",
      expect.objectContaining({ is_enabled: false }),
    );
    fireEvent.click(screen.getByRole("button", { name: "NBA" }));
    expect(screen.getByRole("switch", { name: "Game start alerts" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "WNBA" }));
    expect(screen.getByRole("switch", { name: "Game start alerts" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByText("Last 7 days · 4 events")).toBeInTheDocument();
    expect(apiMocks.listAlertHistory).toHaveBeenCalledTimes(1);
  });

  it("preserves the selected league on refresh and falls back when it is disabled", async () => {
    let poll: (() => void) | undefined;
    const realSetInterval = window.setInterval.bind(window);
    vi.spyOn(window, "setInterval").mockImplementation((callback, delay) => {
      if (delay === 120_000) {
        poll = callback as () => void;
        return 42;
      }
      return realSetInterval(callback, delay);
    });
    apiMocks.listAlertPreferences.mockResolvedValue(preferenceGroups);
    apiMocks.listAlertHistory.mockResolvedValue({ items: [] });
    render(<AlertsView token="token" />);
    fireEvent.click(await screen.findByRole("button", { name: "MLB" }));
    await act(async () => {
      await poll?.();
    });
    expect(screen.getByRole("button", { name: "MLB" })).toHaveAttribute("aria-pressed", "true");
    apiMocks.listAlertPreferences.mockResolvedValue(
      preferenceGroups.filter((group) => group.competition !== "MLB"),
    );
    await act(async () => {
      await poll?.();
    });
    expect(screen.getByRole("button", { name: "NBA" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "MLB" })).toBeNull();
  });
});
