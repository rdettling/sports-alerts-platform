import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DevToolsView } from "./DevToolsView";

const listTeamsMock = vi.fn(async () => [
  { id: 1, external_team_id: "1610612737", league: "NBA", name: "Atlanta Hawks", abbreviation: "ATL" },
  { id: 2, external_team_id: "1610612738", league: "NBA", name: "Boston Celtics", abbreviation: "BOS" },
  { id: 3, external_team_id: "MIA", league: "MLB", name: "Miami Marlins", abbreviation: "MIA" },
  { id: 4, external_team_id: "TOR", league: "MLB", name: "Toronto Blue Jays", abbreviation: "TOR" },
  { id: 5, external_team_id: "203", league: "WORLD_CUP", name: "Mexico", abbreviation: "MEX" },
  { id: 6, external_team_id: "660", league: "WORLD_CUP", name: "United States", abbreviation: "USA" },
]);

const sendDevTestEmailMock = vi.fn(async ({ league, alert_type }: { league: "NBA" | "MLB" | "WORLD_CUP"; alert_type: string }) => ({
  id: 1,
  game_id: 100,
  league,
  alert_type,
  delivery_status: "pending",
}));

vi.mock("../../../shared/api", () => ({
  listTeams: () => listTeamsMock(),
  listLeagues: vi.fn(async () => [
    { league: "NBA", label: "NBA", badge_label: "NBA", alert_types: ["game_start", "close_game_late", "final_result"], is_enabled: true },
    { league: "MLB", label: "MLB", badge_label: "MLB", alert_types: ["game_start", "inning_start", "final_result"], is_enabled: true },
    { league: "WORLD_CUP", label: "World Cup", badge_label: "WC", alert_types: ["game_start", "second_half_start", "extra_time_start", "penalty_kicks", "score_changed", "final_result"], is_enabled: true },
  ]),
  sendDevTestEmail: (_token: string, payload: { league: "NBA" | "MLB" | "WORLD_CUP"; alert_type: string }) =>
    sendDevTestEmailMock(payload),
}));

describe("DevToolsView", () => {
  it("switches visible alert actions by league", async () => {
    listTeamsMock.mockImplementationOnce(async () => [
      { id: 1, external_team_id: "1610612737", league: "NBA", name: "Atlanta Hawks", abbreviation: "ATL" },
      { id: 2, external_team_id: "1610612738", league: "NBA", name: "Boston Celtics", abbreviation: "BOS" },
      { id: 3, external_team_id: "ATH", league: "MLB", name: "Athletics", abbreviation: "ATH" },
      { id: 4, external_team_id: "ARI", league: "MLB", name: "Arizona Diamondbacks", abbreviation: "ARI" },
      { id: 5, external_team_id: "TOR", league: "MLB", name: "Toronto Blue Jays", abbreviation: "TOR" },
      { id: 6, external_team_id: "MIA", league: "MLB", name: "Miami Marlins", abbreviation: "MIA" },
      { id: 7, external_team_id: "203", league: "WORLD_CUP", name: "Mexico", abbreviation: "MEX" },
      { id: 8, external_team_id: "660", league: "WORLD_CUP", name: "United States", abbreviation: "USA" },
    ]);

    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByText("Synthetic matchup (NBA)")).toBeInTheDocument());
    expect(screen.getByText("Close game late alert")).toBeInTheDocument();
    expect(screen.queryByText("Inning start alert")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));

    await waitFor(() => expect(screen.getByText("Synthetic matchup (MLB)")).toBeInTheDocument());
    expect(screen.getByText("Inning start alert")).toBeInTheDocument();
    expect(screen.queryByText("Close game late alert")).toBeNull();
    expect(screen.getByText("MIA")).toBeInTheDocument();
    expect(screen.getByText("TOR")).toBeInTheDocument();
  });

  it("sends selected league with alert type", async () => {
    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByText("Synthetic matchup (NBA)")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Close game late alert"));
    await waitFor(() => expect(sendDevTestEmailMock).toHaveBeenCalledWith({ league: "NBA", alert_type: "close_game_late" }));

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    await waitFor(() => expect(screen.getByText("Inning start alert")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Inning start alert"));
    await waitFor(() => expect(sendDevTestEmailMock).toHaveBeenCalledWith({ league: "MLB", alert_type: "inning_start" }));
  });

  it("shows World Cup with only supported alerts", async () => {
    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "World Cup" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "World Cup" }));

    await waitFor(() => expect(screen.getByText("Synthetic matchup (World Cup)")).toBeInTheDocument());
    expect(screen.getByText("Game start alert")).toBeInTheDocument();
    expect(screen.getByText("Second half start alert")).toBeInTheDocument();
    expect(screen.getByText("Extra time start alert")).toBeInTheDocument();
    expect(screen.getByText("Penalty kicks alert")).toBeInTheDocument();
    expect(screen.getByText("Final result alert")).toBeInTheDocument();
    expect(screen.getByText("Score change alert")).toBeInTheDocument();
    expect(screen.queryByText("Close game late alert")).toBeNull();
    expect(screen.queryByText("Inning start alert")).toBeNull();
  });
});
