import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type CompetitionSetting } from "../../../shared/api";
import { basketballCompetition, baseballCompetition } from "./admin/admin-test-fixtures";
import { AdminTestAlertsPanel } from "./AdminTestAlertsPanel";

const sendAdminTestAlertMock = vi.hoisted(() => vi.fn());

vi.mock("../../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../../shared/api")>("../../../shared/api");
  return { ...actual, sendAdminTestAlert: sendAdminTestAlertMock };
});

const items: CompetitionSetting[] = [
  { ...basketballCompetition, competition: "NBA", label: "NBA", badge_label: "NBA" },
  {
    ...basketballCompetition,
    competition: "NFL",
    sport: "football",
    label: "NFL",
    badge_label: "NFL",
    is_enabled: false,
  },
  baseballCompetition,
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

    expect(screen.queryByRole("option", { name: "NFL" })).toBeNull();
    expect(screen.getByText("Close game late")).toBeInTheDocument();
    expect(screen.queryByText("Inning start")).toBeNull();

    fireEvent.change(screen.getByRole("combobox", { name: "League" }), {
      target: { value: "MLB" },
    });
    expect(screen.getByText("Inning start")).toBeInTheDocument();
    expect(screen.queryByText("Close game late")).toBeNull();
  });

  it("sends the selected test and reports channel outcomes", async () => {
    render(<AdminTestAlertsPanel token="token" items={items} />);

    fireEvent.change(screen.getByRole("combobox", { name: "Alert type" }), {
      target: { value: "close_game_late" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send test alert" }));

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

    fireEvent.click(screen.getByRole("button", { name: "Send test alert" }));
    expect(await screen.findByText("Test delivery failed")).toBeInTheDocument();
  });

  it("shows an empty state when every competition is disabled", () => {
    render(
      <AdminTestAlertsPanel
        token="token"
        items={items.map((item) => ({ ...item, is_enabled: false }))}
      />,
    );

    expect(screen.getByText("Enable a league in Leagues to send test alerts.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send test alert" })).toBeDisabled();
  });
  it("retains supported alert types, falls back for unsupported types, and clears feedback", async () => {
    render(<AdminTestAlertsPanel token="token" items={items} />);
    const league = screen.getByRole("combobox", { name: "League" });
    const type = screen.getByRole("combobox", { name: "Alert type" });
    expect(league).toHaveValue("NBA");
    expect(type).toHaveValue("game_start");
    fireEvent.change(type, { target: { value: "final_result" } });
    fireEvent.change(league, { target: { value: "MLB" } });
    expect(type).toHaveValue("final_result");
    fireEvent.change(type, { target: { value: "inning_start" } });
    fireEvent.change(league, { target: { value: "NBA" } });
    expect(type).toHaveValue("game_start");
    fireEvent.click(screen.getByRole("button", { name: "Send test alert" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Game start test for NBA: email sent.",
    );
    fireEvent.change(type, { target: { value: "final_result" } });
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("blocks duplicate submissions and disables inputs while sending", async () => {
    sendAdminTestAlertMock.mockImplementation(() => new Promise(() => {}));
    const { container } = render(<AdminTestAlertsPanel token="token" items={items} />);
    fireEvent.submit(container.querySelector("form")!);
    fireEvent.submit(container.querySelector("form")!);
    expect(sendAdminTestAlertMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("combobox", { name: "League" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Alert type" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
  });

  it("handles a selected league becoming disabled and missing alert types", () => {
    const view = render(<AdminTestAlertsPanel token="token" items={items} />);
    view.rerender(
      <AdminTestAlertsPanel
        token="token"
        items={items.map((item) => ({
          ...item,
          is_enabled: item.competition === "MLB",
          alert_types: [],
        }))}
      />,
    );
    expect(screen.getByRole("combobox", { name: "League" })).toHaveValue("MLB");
    expect(screen.getByRole("combobox", { name: "Alert type" })).toBeDisabled();
    expect(screen.getByText("This league has no supported test alerts.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send test alert" })).toBeDisabled();
  });
});
