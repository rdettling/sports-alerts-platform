import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DevToolsView } from "./DevToolsView";

const listTeamsMock = vi.fn(async () => [
  { id: 1, external_team_id: "1610612737", league: "NBA", name: "Atlanta Hawks", abbreviation: "ATL" },
  { id: 2, external_team_id: "1610612738", league: "NBA", name: "Boston Celtics", abbreviation: "BOS" },
  { id: 3, external_team_id: "MIA", league: "MLB", name: "Miami Marlins", abbreviation: "MIA" },
  { id: 4, external_team_id: "TOR", league: "MLB", name: "Toronto Blue Jays", abbreviation: "TOR" },
]);

const sendDevTestEmailMock = vi.fn(async ({ league, alert_type }: { league: "NBA" | "MLB"; alert_type: string }) => ({
  id: 1,
  game_id: 100,
  league,
  alert_type,
  delivery_status: "pending",
}));

vi.mock("../../../shared/api", () => ({
  listTeams: () => listTeamsMock(),
  listLeagues: vi.fn(async () => [
    { league: "NBA", is_enabled: true },
    { league: "MLB", is_enabled: true },
  ]),
  sendDevTestEmail: (_token: string, payload: { league: "NBA" | "MLB"; alert_type: string }) =>
    sendDevTestEmailMock(payload),
}));

describe("DevToolsView", () => {
  it("switches visible alert actions by league", async () => {
    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByText("Synthetic matchup (NBA)")).toBeInTheDocument());
    expect(screen.getByText("Close-game alert")).toBeInTheDocument();
    expect(screen.queryByText("Inning-start alert")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));

    await waitFor(() => expect(screen.getByText("Synthetic matchup (MLB)")).toBeInTheDocument());
    expect(screen.getByText("Inning-start alert")).toBeInTheDocument();
    expect(screen.queryByText("Close-game alert")).toBeNull();
    expect(screen.getByText("MIA")).toBeInTheDocument();
    expect(screen.getByText("TOR")).toBeInTheDocument();
  });

  it("sends selected league with alert type", async () => {
    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByText("Synthetic matchup (NBA)")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Close-game alert"));
    await waitFor(() => expect(sendDevTestEmailMock).toHaveBeenCalledWith({ league: "NBA", alert_type: "close_game_late" }));

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    await waitFor(() => expect(screen.getByText("Inning-start alert")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Inning-start alert"));
    await waitFor(() => expect(sendDevTestEmailMock).toHaveBeenCalledWith({ league: "MLB", alert_type: "inning_start" }));
  });
});
