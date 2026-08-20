import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AlertsView } from "./AlertsView";

const apiMocks = vi.hoisted(() => ({
  listAlertHistory: vi.fn(),
  listAlertPreferences: vi.fn(),
  updateAlertPreference: vi.fn(),
}));

vi.mock("../../../shared/api", () => apiMocks);

vi.mock("./alerts/AlertDeliverySettings", () => ({
  AlertDeliverySettings: () => <section aria-label="Delivery settings">Delivery settings</section>,
}));

const basketballPreferences = [
  {
    sport: "basketball",
    alert_type: "game_start",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    inning_start_threshold: null,
  },
  {
    sport: "basketball",
    alert_type: "close_game_late",
    is_enabled: true,
    close_game_margin_threshold: 5,
    close_game_time_threshold_seconds: 300,
    inning_start_threshold: null,
  },
  {
    sport: "basketball",
    alert_type: "overtime_start",
    is_enabled: false,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    inning_start_threshold: null,
  },
  {
    sport: "basketball",
    alert_type: "final_result",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    inning_start_threshold: null,
  },
];

const baseballPreferences = [
  {
    sport: "baseball",
    alert_type: "game_start",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    inning_start_threshold: null,
  },
  {
    sport: "baseball",
    alert_type: "inning_start",
    is_enabled: true,
    close_game_margin_threshold: null,
    close_game_time_threshold_seconds: null,
    inning_start_threshold: 7,
  },
];

const preferenceGroups = [
  { sport: "basketball", preferences: basketballPreferences },
  { sport: "baseball", preferences: baseballPreferences },
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
    apiMocks.updateAlertPreference.mockImplementation((_token, sport, alertType, payload) =>
      Promise.resolve({ sport, alert_type: alertType, ...payload }),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads the first active sport and groups recent history by local day", async () => {
    render(<AlertsView token="token" />);
    expect(screen.getByText("Loading alerts...")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Alert Rules" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Basketball" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("Close game late")).toBeInTheDocument();
    expect(screen.queryByText("Score change")).toBeNull();
    expect(screen.getByRole("switch", { name: "Overtime start alerts" })).toHaveAttribute(
      "aria-checked",
      "false",
    );

    expect(screen.getByText("Last 7 days · 3 events")).toBeInTheDocument();
    const today = screen.getByRole("region", { name: "Today" });
    expect(within(today).getAllByRole("listitem")[0]).toHaveTextContent("NY @ LV");
    expect(within(today).getAllByRole("listitem")[1]).toHaveTextContent("ATL @ SEA");
    expect(within(today).getByText("Email sent")).toBeInTheDocument();
    expect(within(today).getByText("Push pending")).toBeInTheDocument();
    expect(within(today).getByText("Email sent")).toHaveClass("status-sent");
    expect(within(today).getByText("Push pending")).toHaveClass("status-pending");
    expect(within(today).getByText("—")).toBeInTheDocument();
    const yesterday = screen.getByRole("region", { name: "Yesterday" });
    expect(yesterday).toHaveTextContent("Email failed");
    expect(within(yesterday).getByText("Email failed")).toHaveClass("status-failed");
  });

  it("switches sports and shows that sport's rules", async () => {
    render(<AlertsView token="token" />);
    fireEvent.click(await screen.findByRole("button", { name: "Baseball" }));

    expect(screen.getByRole("button", { name: "Baseball" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("switch", { name: "Inning start alerts" })).toBeInTheDocument();
    expect(screen.queryByText("Close game late")).toBeNull();
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
      expect(apiMocks.updateAlertPreference).toHaveBeenCalledWith(
        "token",
        "basketball",
        "game_start",
        {
          is_enabled: false,
          close_game_margin_threshold: null,
          close_game_time_threshold_seconds: null,
          inning_start_threshold: null,
        },
      ),
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
        "basketball",
        "close_game_late",
        {
          is_enabled: true,
          close_game_margin_threshold: 5,
          close_game_time_threshold_seconds: 600,
          inning_start_threshold: null,
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
    expect(await screen.findByText("No rules for this sport.")).toBeInTheDocument();
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
