import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamsView } from "./TeamsView";

const apiMocks = vi.hoisted(() => ({
  followTeam: vi.fn(),
  unfollowTeam: vi.fn(),
  listFollows: vi.fn(),
  listLeagues: vi.fn(),
  listTeams: vi.fn(),
}));

vi.mock("../../../shared/api", () => apiMocks);

const teams = [
  { id: 1, external_team_id: "1", league: "NBA", name: "Atlanta Hawks", abbreviation: "ATL" },
  { id: 2, external_team_id: "2", league: "NBA", name: "Boston Celtics", abbreviation: "BOS" },
  { id: 3, external_team_id: "3", league: "MLB", name: "New York Yankees", abbreviation: "NYY" },
];

const leagues = [
  { league: "NBA", sport: "basketball", label: "NBA", badge_label: "NBA", alert_types: [], live_sync_interval_seconds: 120, default_test_matchup: ["ATL", "BOS"], is_enabled: true },
  { league: "MLB", sport: "baseball", label: "MLB", badge_label: "MLB", alert_types: [], live_sync_interval_seconds: 300, default_test_matchup: ["NYY", "BOS"], is_enabled: true },
];

function renderTeamsView(token: string | null, onSignInRequired = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    ...render(
      <QueryClientProvider client={client}>
        <TeamsView token={token} onSignInRequired={onSignInRequired} />
      </QueryClientProvider>,
    ),
    onSignInRequired,
  };
}

describe("TeamsView", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.listTeams.mockResolvedValue(teams);
    apiMocks.listLeagues.mockResolvedValue(leagues);
    apiMocks.listFollows.mockResolvedValue({ teams: [], games: [] });
    apiMocks.followTeam.mockResolvedValue({ status: "ok" });
    apiMocks.unfollowTeam.mockResolvedValue({ status: "ok" });
  });

  it("defaults to the first league and searches within the selected league", async () => {
    renderTeamsView(null);

    expect(await screen.findByText("Boston Celtics")).toBeInTheDocument();
    expect(screen.queryByText("New York Yankees")).toBeNull();
    expect(apiMocks.listFollows).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "NBA" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("New York Yankees")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "NBA" })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    fireEvent.change(screen.getByLabelText("Search teams"), { target: { value: "Boston" } });
    expect(screen.getByText("No teams match this filter.")).toBeInTheDocument();
  });

  it("prompts a guest to sign in without calling the follow API", async () => {
    const { onSignInRequired } = renderTeamsView(null);

    fireEvent.click((await screen.findAllByRole("button", { name: "Follow" }))[0]);
    expect(onSignInRequired).toHaveBeenCalledTimes(1);
    expect(apiMocks.followTeam).not.toHaveBeenCalled();
  });

  it("sorts followed teams first and unfollows them", async () => {
    let followedTeams = [teams[1]];
    apiMocks.listFollows.mockImplementation(async () => ({ teams: followedTeams, games: [] }));
    apiMocks.unfollowTeam.mockImplementation(async () => {
      followedTeams = [];
      return { status: "ok" };
    });
    renderTeamsView("token");

    const rows = await screen.findAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Boston Celtics");

    fireEvent.click(screen.getByRole("button", { name: "Unfollow" }));
    await waitFor(() => expect(apiMocks.unfollowTeam).toHaveBeenCalledWith("token", 2));
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Follow" })).toHaveLength(2));
  });

  it("follows a team and refreshes its state", async () => {
    let followedTeams: typeof teams = [];
    apiMocks.listFollows.mockImplementation(async () => ({ teams: followedTeams, games: [] }));
    apiMocks.followTeam.mockImplementation(async (_token: string, teamId: number) => {
      followedTeams = teams.filter((team) => team.id === teamId);
      return { status: "ok" };
    });
    renderTeamsView("token");

    fireEvent.click((await screen.findAllByRole("button", { name: "Follow" }))[0]);

    await waitFor(() => expect(apiMocks.followTeam).toHaveBeenCalledWith("token", 1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Unfollow" })).toBeInTheDocument());
  });
});
