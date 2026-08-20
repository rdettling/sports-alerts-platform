import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type CompetitionSetting } from "../../../shared/api";
import { AdminTestAlertsPanel } from "./AdminTestAlertsPanel";

const sendAdminTestAlertMock = vi.hoisted(() => vi.fn());

vi.mock("../../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../../shared/api")>("../../../shared/api");
  return { ...actual, sendAdminTestAlert: sendAdminTestAlertMock };
});

const items: CompetitionSetting[] = [
  {
    competition: "NBA",
    sport: "basketball",
    label: "NBA",
    badge_label: "NBA",
    alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
  {
    competition: "NFL",
    sport: "football",
    label: "NFL",
    badge_label: "NFL",
    alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
    live_sync_interval_seconds: 120,
    is_enabled: false,
  },
  {
    competition: "MLB",
    sport: "baseball",
    label: "MLB",
    badge_label: "MLB",
    alert_types: ["game_start", "inning_start", "extra_innings_start", "final_result"],
    live_sync_interval_seconds: 300,
    is_enabled: true,
  },
];

describe("AdminTestAlertsPanel", () => {
  beforeEach(() => {
    sendAdminTestAlertMock.mockReset();
    sendAdminTestAlertMock.mockImplementation(async (_token, payload) => ({
      ...payload,
      deliveries: [{ channel: "email", status: "sent", attempted_at: "2026-08-19T00:00:00Z" }],
    }));
  });

  it("shows only enabled competitions and their supported alert actions", () => {
    render(<AdminTestAlertsPanel token="token" items={items} />);

    expect(screen.queryByRole("button", { name: "NFL" })).toBeNull();
    expect(screen.getByText("Close game late test alert")).toBeInTheDocument();
    expect(screen.queryByText("Inning start test alert")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    expect(screen.getByText("Inning start test alert")).toBeInTheDocument();
    expect(screen.queryByText("Close game late test alert")).toBeNull();
  });

  it("sends the selected test and reports channel outcomes", async () => {
    render(<AdminTestAlertsPanel token="token" items={items} />);

    fireEvent.click(screen.getByText("Close game late test alert"));

    await waitFor(() =>
      expect(sendAdminTestAlertMock).toHaveBeenCalledWith("token", {
        competition: "NBA",
        alert_type: "close_game_late",
      }),
    );
    expect(
      await screen.findByText("Close game late test for NBA: email sent."),
    ).toBeInTheDocument();
  });

  it("reports request failures", async () => {
    sendAdminTestAlertMock.mockRejectedValueOnce(new Error("Test delivery failed"));
    render(<AdminTestAlertsPanel token="token" items={items} />);

    fireEvent.click(screen.getByText("Game start test alert"));
    expect(await screen.findByText("Test delivery failed")).toBeInTheDocument();
  });

  it("shows an empty state when every competition is disabled", () => {
    render(
      <AdminTestAlertsPanel
        token="token"
        items={items.map((item) => ({ ...item, is_enabled: false }))}
      />,
    );

    expect(screen.getByText("Enable a competition to send test alerts.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Test alert actions")).toBeNull();
  });
});
