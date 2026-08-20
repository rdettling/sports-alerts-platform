import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  { id: 2, external_team_id: "2", league: "NBA", name: "Boston Celtics", abbreviation: "BOS" },
  { id: 1, external_team_id: "1", league: "NBA", name: "Atlanta Hawks", abbreviation: "ATL" },
  { id: 3, external_team_id: "3", league: "MLB", name: "New York Yankees", abbreviation: "NYY" },
  {
    id: 4,
    external_team_id: "4",
    league: "MLS",
    name: "New England Revolution",
    abbreviation: "NE",
  },
];

const leagues = [
  {
    league: "NBA",
    sport: "basketball",
    label: "NBA",
    badge_label: "NBA",
    alert_types: [],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
  {
    league: "MLB",
    sport: "baseball",
    label: "MLB",
    badge_label: "MLB",
    alert_types: [],
    live_sync_interval_seconds: 300,
    is_enabled: true,
  },
  {
    league: "MLS",
    sport: "soccer",
    label: "MLS",
    badge_label: "MLS",
    alert_types: [],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
];

function renderTeamsView(token: string | null, onSignInRequired = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    ...render(
      <QueryClientProvider client={client}>
        <TeamsView token={token} onSignInRequired={onSignInRequired} />
      </QueryClientProvider>,
    ),
    client,
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

  it("defaults to all teams and groups them in active-league order", async () => {
    renderTeamsView(null);

    expect(await screen.findByText("Boston Celtics")).toBeInTheDocument();
    expect(apiMocks.listFollows).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("group", { name: "Team scope" })).toBeNull();
    expect(
      screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent),
    ).toEqual(["NBA", "MLB", "MLS"]);

    const nba = screen.getByRole("region", { name: "NBA" });
    expect(within(nba).getByText("2 teams")).toBeInTheDocument();
    expect(within(nba).getAllByRole("listitem")[0]).toHaveTextContent("Atlanta Hawks");
    expect(screen.getByRole("region", { name: "MLB" })).toHaveTextContent("1 team");
    expect(screen.getByRole("region", { name: "MLS" })).toHaveTextContent("1 team");
  });

  it("filters by league and keeps search text when filters change", async () => {
    renderTeamsView(null);
    await screen.findByText("Boston Celtics");

    fireEvent.change(screen.getByRole("searchbox", { name: "Search teams" }), {
      target: { value: "Boston" },
    });
    expect(screen.getByRole("region", { name: "NBA" })).toHaveTextContent("1 team");
    expect(screen.queryByRole("region", { name: "MLB" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    expect(screen.getByRole("searchbox", { name: "Search teams" })).toHaveValue("Boston");
    expect(screen.getByText("No teams match this filter.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("Boston Celtics")).toBeInTheDocument();
  });

  it("shows an authenticated Following scope with its count", async () => {
    apiMocks.listFollows.mockResolvedValue({ teams: [teams[1]], games: [] });
    renderTeamsView("token");

    const following = await screen.findByRole("button", { name: "Following 1" });
    expect(screen.getByRole("button", { name: "All teams" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(following);
    expect(following).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Atlanta Hawks")).toBeInTheDocument();
    expect(screen.queryByText("Boston Celtics")).toBeNull();
    expect(screen.queryByRole("region", { name: "MLB" })).toBeNull();
  });

  it("returns to all teams if authentication disappears", async () => {
    apiMocks.listFollows.mockResolvedValue({ teams: [teams[1]], games: [] });
    const view = renderTeamsView("token");

    fireEvent.click(await screen.findByRole("button", { name: "Following 1" }));
    expect(screen.queryByText("Boston Celtics")).toBeNull();

    view.rerender(
      <QueryClientProvider client={view.client}>
        <TeamsView token={null} onSignInRequired={view.onSignInRequired} />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.queryByRole("group", { name: "Team scope" })).toBeNull());
    expect(await screen.findByText("Boston Celtics")).toBeInTheDocument();
    expect(screen.getByText("New York Yankees")).toBeInTheDocument();
  });

  it("sorts followed teams first within their league and unfollows them", async () => {
    let followedTeams = [teams[0]];
    apiMocks.listFollows.mockImplementation(async () => ({ teams: followedTeams, games: [] }));
    apiMocks.unfollowTeam.mockImplementation(async () => {
      followedTeams = [];
      return { status: "ok" };
    });
    renderTeamsView("token");

    const nba = await screen.findByRole("region", { name: "NBA" });
    expect(within(nba).getAllByRole("listitem")[0]).toHaveTextContent("Boston Celtics");

    fireEvent.click(screen.getByRole("button", { name: "Unfollow" }));
    await waitFor(() => expect(apiMocks.unfollowTeam).toHaveBeenCalledWith("token", 2));
    await waitFor(() => expect(screen.getByRole("button", { name: "Following 0" })).toBeVisible());
    expect(within(nba).getAllByRole("listitem")[0]).toHaveTextContent("Atlanta Hawks");
  });

  it("prompts a guest to sign in without calling the follow API", async () => {
    const { onSignInRequired } = renderTeamsView(null);

    fireEvent.click((await screen.findAllByRole("button", { name: "Follow" }))[0]);
    expect(onSignInRequired).toHaveBeenCalledTimes(1);
    expect(apiMocks.followTeam).not.toHaveBeenCalled();
  });

  it("follows a team and refreshes both team state and followed count", async () => {
    let followedTeams: typeof teams = [];
    apiMocks.listFollows.mockImplementation(async () => ({ teams: followedTeams, games: [] }));
    apiMocks.followTeam.mockImplementation(async (_token: string, teamId: number) => {
      followedTeams = teams.filter((team) => team.id === teamId);
      return { status: "ok" };
    });
    renderTeamsView("token");

    fireEvent.click((await screen.findAllByRole("button", { name: "Follow" }))[0]);

    await waitFor(() => expect(apiMocks.followTeam).toHaveBeenCalledWith("token", 1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Unfollow" })).toBeVisible());
    expect(screen.getByRole("button", { name: "Following 1" })).toBeVisible();
  });

  it("shows Saving and disables actions while a follow change is pending", async () => {
    let finishFollow: (() => void) | undefined;
    apiMocks.followTeam.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishFollow = () => resolve({ status: "ok" });
        }),
    );
    renderTeamsView("token");

    fireEvent.click((await screen.findAllByRole("button", { name: "Follow" }))[0]);
    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
    screen
      .getAllByRole("button", { name: "Follow" })
      .forEach((button) => expect(button).toBeDisabled());

    await waitFor(() => expect(apiMocks.followTeam).toHaveBeenCalled());
    finishFollow?.();
    await waitFor(() => expect(screen.queryByRole("button", { name: "Saving..." })).toBeNull());
  });

  it("renders loading, error, and scope-specific empty states", async () => {
    apiMocks.listTeams.mockImplementationOnce(() => new Promise(() => undefined));
    const loadingView = renderTeamsView(null);
    expect(screen.getByText("Loading teams...")).toBeInTheDocument();
    loadingView.unmount();

    apiMocks.listTeams.mockRejectedValueOnce(new Error("Teams unavailable"));
    const errorView = renderTeamsView(null);
    expect(await screen.findByText("Teams unavailable")).toBeInTheDocument();
    errorView.unmount();

    renderTeamsView("token");
    fireEvent.click(await screen.findByRole("button", { name: "Following 0" }));
    expect(screen.getByText("No followed teams match this filter.")).toBeInTheDocument();
  });
});
