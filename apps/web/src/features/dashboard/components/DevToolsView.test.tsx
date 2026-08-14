import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DevToolsView } from "./DevToolsView";

const listTeamsMock = vi.fn(async () => [
  {
    id: 1,
    external_team_id: "1610612737",
    league: "NBA",
    name: "Atlanta Hawks",
    abbreviation: "ATL",
  },
  {
    id: 2,
    external_team_id: "1610612738",
    league: "NBA",
    name: "Boston Celtics",
    abbreviation: "BOS",
  },
  { id: 3, external_team_id: "9", league: "WNBA", name: "New York Liberty", abbreviation: "NY" },
  { id: 4, external_team_id: "17", league: "WNBA", name: "Las Vegas Aces", abbreviation: "LV" },
  { id: 5, external_team_id: "MIA", league: "MLB", name: "Miami Marlins", abbreviation: "MIA" },
  { id: 6, external_team_id: "TOR", league: "MLB", name: "Toronto Blue Jays", abbreviation: "TOR" },
  { id: 7, external_team_id: "18966", league: "MLS", name: "LAFC", abbreviation: "LAFC" },
  { id: 8, external_team_id: "187", league: "MLS", name: "LA Galaxy", abbreviation: "LA" },
  { id: 9, external_team_id: "203", league: "WORLD_CUP", name: "Mexico", abbreviation: "MEX" },
  {
    id: 10,
    external_team_id: "660",
    league: "WORLD_CUP",
    name: "United States",
    abbreviation: "USA",
  },
]);

const sendDevTestAlertMock = vi.fn(
  async ({
    league,
    alert_type,
  }: {
    league: "NBA" | "WNBA" | "MLB" | "MLS" | "WORLD_CUP";
    alert_type: string;
  }) => ({
    id: 1,
    game_id: 100,
    league,
    alert_type,
    deliveries: [{ channel: "email", status: "sent", attempted_at: new Date().toISOString() }],
  }),
);

vi.mock("../../../shared/api", () => ({
  listTeams: () => listTeamsMock(),
  listLeagues: vi.fn(async () => [
    {
      league: "NBA",
      sport: "basketball",
      label: "NBA",
      badge_label: "NBA",
      alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
      live_sync_interval_seconds: 120,
      default_test_matchup: ["ATL", "BOS"],
      is_enabled: true,
    },
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
    {
      league: "MLS",
      sport: "soccer",
      label: "MLS",
      badge_label: "MLS",
      alert_types: [
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
      ],
      live_sync_interval_seconds: 180,
      default_test_matchup: ["LAFC", "LA"],
      is_enabled: true,
    },
    {
      league: "WORLD_CUP",
      sport: "soccer",
      label: "World Cup",
      badge_label: "WC",
      alert_types: [
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
      ],
      live_sync_interval_seconds: 180,
      default_test_matchup: ["MEX", "USA"],
      is_enabled: true,
    },
  ]),
  sendDevTestAlert: (
    _token: string,
    payload: { league: "NBA" | "WNBA" | "MLB" | "MLS" | "WORLD_CUP"; alert_type: string },
  ) => sendDevTestAlertMock(payload),
}));

describe("DevToolsView", () => {
  it("switches visible alert actions by league", async () => {
    listTeamsMock.mockImplementationOnce(async () => [
      {
        id: 1,
        external_team_id: "1610612737",
        league: "NBA",
        name: "Atlanta Hawks",
        abbreviation: "ATL",
      },
      {
        id: 2,
        external_team_id: "1610612738",
        league: "NBA",
        name: "Boston Celtics",
        abbreviation: "BOS",
      },
      { id: 3, external_team_id: "ATH", league: "MLB", name: "Athletics", abbreviation: "ATH" },
      {
        id: 4,
        external_team_id: "ARI",
        league: "MLB",
        name: "Arizona Diamondbacks",
        abbreviation: "ARI",
      },
      {
        id: 5,
        external_team_id: "TOR",
        league: "MLB",
        name: "Toronto Blue Jays",
        abbreviation: "TOR",
      },
      { id: 6, external_team_id: "MIA", league: "MLB", name: "Miami Marlins", abbreviation: "MIA" },
      { id: 7, external_team_id: "18966", league: "MLS", name: "LAFC", abbreviation: "LAFC" },
      { id: 8, external_team_id: "187", league: "MLS", name: "LA Galaxy", abbreviation: "LA" },
      { id: 9, external_team_id: "203", league: "WORLD_CUP", name: "Mexico", abbreviation: "MEX" },
      {
        id: 10,
        external_team_id: "660",
        league: "WORLD_CUP",
        name: "United States",
        abbreviation: "USA",
      },
    ]);

    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByText("Synthetic matchup (NBA)")).toBeInTheDocument());
    expect(screen.getByText("Close game late test alert")).toBeInTheDocument();
    expect(screen.queryByText("Inning start test alert")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));

    await waitFor(() => expect(screen.getByText("Synthetic matchup (MLB)")).toBeInTheDocument());
    expect(screen.getByText("Inning start test alert")).toBeInTheDocument();
    expect(screen.queryByText("Close game late test alert")).toBeNull();
    expect(screen.getByText("MIA")).toBeInTheDocument();
    expect(screen.getByText("TOR")).toBeInTheDocument();
  });

  it("sends selected league with alert type", async () => {
    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByText("Synthetic matchup (NBA)")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Close game late test alert"));
    await waitFor(() =>
      expect(sendDevTestAlertMock).toHaveBeenCalledWith({
        league: "NBA",
        alert_type: "close_game_late",
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    await waitFor(() => expect(screen.getByText("Inning start test alert")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Inning start test alert"));
    await waitFor(() =>
      expect(sendDevTestAlertMock).toHaveBeenCalledWith({
        league: "MLB",
        alert_type: "inning_start",
      }),
    );
  });

  it("shows World Cup with only supported alerts", async () => {
    render(<DevToolsView token="token" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "World Cup" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "World Cup" }));

    await waitFor(() =>
      expect(screen.getByText("Synthetic matchup (World Cup)")).toBeInTheDocument(),
    );
    expect(screen.getByText("Game start test alert")).toBeInTheDocument();
    expect(screen.getByText("Second half start test alert")).toBeInTheDocument();
    expect(screen.getByText("Extra time start test alert")).toBeInTheDocument();
    expect(screen.getByText("Penalty kicks test alert")).toBeInTheDocument();
    expect(screen.getByText("Final result test alert")).toBeInTheDocument();
    expect(screen.getByText("Score change test alert")).toBeInTheDocument();
    expect(screen.queryByText("Close game late test alert")).toBeNull();
    expect(screen.queryByText("Inning start test alert")).toBeNull();
  });

  it("shows the complete shared soccer alert set for MLS", async () => {
    render(<DevToolsView token="token" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "MLS" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "MLS" }));

    await waitFor(() => expect(screen.getByText("Synthetic matchup (MLS)")).toBeInTheDocument());
    expect(screen.getByText("LAFC")).toBeInTheDocument();
    expect(screen.getByText("LA")).toBeInTheDocument();
    expect(screen.getByText("Extra time start test alert")).toBeInTheDocument();
    expect(screen.getByText("Penalty kicks test alert")).toBeInTheDocument();
    expect(screen.getByText("Score change test alert")).toBeInTheDocument();
  });

  it("shows the shared basketball alert set for WNBA", async () => {
    render(<DevToolsView token="token" />);

    fireEvent.click(await screen.findByRole("button", { name: "WNBA" }));

    await waitFor(() => expect(screen.getByText("Synthetic matchup (WNBA)")).toBeInTheDocument());
    expect(screen.getByText("NY")).toBeInTheDocument();
    expect(screen.getByText("LV")).toBeInTheDocument();
    expect(screen.getByText("Close game late test alert")).toBeInTheDocument();
    expect(screen.queryByText("Inning start test alert")).toBeNull();
  });

  it("reports failed test alerts", async () => {
    sendDevTestAlertMock.mockRejectedValueOnce(new Error("Test delivery failed"));
    render(<DevToolsView token="token" />);

    fireEvent.click(await screen.findByText("Game start test alert"));
    expect(await screen.findByText("Test delivery failed")).toBeInTheDocument();
  });
});
