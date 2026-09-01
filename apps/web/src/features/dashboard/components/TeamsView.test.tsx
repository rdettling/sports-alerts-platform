import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamsView } from "./TeamsView";

const apiMocks = vi.hoisted(() => ({
  followTeam: vi.fn(),
  unfollowTeam: vi.fn(),
  listFollows: vi.fn(),
  listCompetitions: vi.fn(),
  listTeams: vi.fn(),
  getCompetitionVisibility: vi.fn(),
  updateCompetitionVisibility: vi.fn(),
}));

vi.mock("../../../shared/api", () => apiMocks);

const teams = [
  {
    id: 2,
    sport: "basketball",
    external_team_id: "2",
    competitions: ["NBA"],
    name: "Boston Celtics",
    abbreviation: "BOS",
  },
  {
    id: 1,
    sport: "basketball",
    external_team_id: "1",
    competitions: ["NBA"],
    name: "Atlanta Hawks",
    abbreviation: "ATL",
  },
  {
    id: 3,
    sport: "baseball",
    external_team_id: "3",
    competitions: ["MLB"],
    name: "New York Yankees",
    abbreviation: "NYY",
  },
  {
    id: 4,
    external_team_id: "4",
    sport: "soccer",
    competitions: ["MLS"],
    name: "New England Revolution",
    abbreviation: "NE",
  },
  {
    id: 5,
    external_team_id: "86",
    sport: "soccer",
    competitions: ["LA_LIGA"],
    name: "Real Madrid",
    abbreviation: "RMA",
  },
  {
    id: 6,
    external_team_id: "359",
    sport: "soccer",
    competitions: ["PREMIER_LEAGUE", "LA_LIGA"],
    name: "Arsenal",
    abbreviation: "ARS",
  },
];

const competitions = [
  {
    competition: "NBA",
    sport: "basketball",
    label: "NBA",
    badge_label: "NBA",
    alert_types: [],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
  {
    competition: "MLB",
    sport: "baseball",
    label: "MLB",
    badge_label: "MLB",
    alert_types: [],
    live_sync_interval_seconds: 300,
    is_enabled: true,
  },
  {
    competition: "MLS",
    sport: "soccer",
    label: "MLS",
    badge_label: "MLS",
    alert_types: [],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
  {
    competition: "LA_LIGA",
    sport: "soccer",
    label: "La Liga",
    badge_label: "LALIGA",
    alert_types: [],
    live_sync_interval_seconds: 180,
    is_enabled: true,
  },
  {
    competition: "PREMIER_LEAGUE",
    sport: "soccer",
    label: "Premier League",
    badge_label: "EPL",
    alert_types: [],
    live_sync_interval_seconds: 180,
    is_enabled: true,
  },
];

const fbsTeams = [
  {
    id: 101,
    sport: "football",
    external_team_id: "333",
    competitions: ["FBS"],
    conference: "SEC",
    name: "Alabama Crimson Tide",
    abbreviation: "ALA",
  },
  {
    id: 102,
    sport: "football",
    external_team_id: "2",
    competitions: ["FBS"],
    conference: "SEC",
    name: "Auburn Tigers",
    abbreviation: "AUB",
  },
  {
    id: 103,
    sport: "football",
    external_team_id: "130",
    competitions: ["FBS"],
    conference: "Big Ten",
    name: "Michigan Wolverines",
    abbreviation: "MICH",
  },
];

const fbsCompetition = {
  competition: "FBS",
  sport: "football",
  label: "College Football",
  badge_label: "FBS",
  alert_types: [],
  live_sync_interval_seconds: 120,
  is_enabled: true,
};

function renderTeamsView(
  token: string | null,
  onSignInRequired = vi.fn(),
  onManageLeagues = vi.fn(),
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    ...render(
      <QueryClientProvider client={client}>
        <TeamsView
          token={token}
          onSignInRequired={onSignInRequired}
          onManageLeagues={onManageLeagues}
        />
      </QueryClientProvider>,
    ),
    client,
    onSignInRequired,
    onManageLeagues,
  };
}

describe("TeamsView", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.listTeams.mockResolvedValue(teams);
    apiMocks.listCompetitions.mockResolvedValue(competitions);
    apiMocks.listFollows.mockResolvedValue({ teams: [], games: [] });
    apiMocks.getCompetitionVisibility.mockResolvedValue({ hidden_competitions: [] });
    apiMocks.updateCompetitionVisibility.mockImplementation(
      async (_token: string, hidden_competitions: string[]) => ({ hidden_competitions }),
    );
    apiMocks.followTeam.mockResolvedValue({ status: "ok" });
    apiMocks.unfollowTeam.mockResolvedValue({ status: "ok" });
  });

  it("shows abbreviation and memberships as quiet inline metadata", async () => {
    renderTeamsView(null);

    expect(await screen.findByText("Boston Celtics")).toBeInTheDocument();
    expect(apiMocks.listFollows).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("group", { name: "Team scope" })).toBeNull();
    const directory = screen.getByRole("region", { name: "All teams" });
    expect(within(directory).getByText("6 teams")).toBeInTheDocument();
    expect(within(directory).getAllByRole("listitem")[0]).toHaveTextContent("Arsenal");
    expect(within(directory).getByText("ARS · EPL · LALIGA")).toBeInTheDocument();
    expect(within(directory).getByText("RMA · LALIGA")).toBeInTheDocument();
  });

  it("filters by competition and keeps search text when filters change", async () => {
    renderTeamsView(null);
    await screen.findByText("Boston Celtics");

    fireEvent.change(screen.getByRole("searchbox", { name: "Search teams" }), {
      target: { value: "Boston" },
    });
    expect(screen.getByRole("region", { name: "All teams" })).toHaveTextContent("1 team");

    fireEvent.click(screen.getByRole("button", { name: "MLB" }));
    expect(screen.getByRole("searchbox", { name: "Search teams" })).toHaveValue("Boston");
    expect(screen.getByText("No teams match this filter.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("Boston Celtics")).toBeInTheDocument();
  });

  it("omits the selected competition from team metadata", async () => {
    renderTeamsView(null);

    fireEvent.click(await screen.findByRole("button", { name: "Premier League" }));

    expect(screen.getByText("ARS · LALIGA")).toBeInTheDocument();
    expect(screen.queryByText(/EPL/)).toBeNull();
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
    expect(screen.getByRole("region", { name: "All teams" })).toHaveTextContent("1 team");
  });

  it("hides league-only teams while retaining visible memberships", async () => {
    apiMocks.getCompetitionVisibility.mockResolvedValue({ hidden_competitions: ["LA_LIGA"] });
    apiMocks.listFollows.mockResolvedValue({ teams: [teams[4]], games: [] });
    renderTeamsView("token");

    expect(await screen.findByText("Arsenal")).toBeInTheDocument();
    expect(screen.queryByText("Real Madrid")).toBeNull();
    expect(screen.queryByRole("button", { name: "La Liga" })).toBeNull();
    expect(screen.getByText("ARS · EPL")).toBeInTheDocument();
    expect(screen.queryByText(/LALIGA/)).toBeNull();
    expect(screen.getByRole("button", { name: "Following 0" })).toBeInTheDocument();
  });

  it("filters cached teams through the current active competition catalog", async () => {
    apiMocks.listCompetitions.mockResolvedValue(
      competitions.filter(({ competition }) => competition !== "LA_LIGA"),
    );
    apiMocks.listFollows.mockResolvedValue({ teams: [teams[4]], games: [] });
    renderTeamsView("token");

    expect(await screen.findByText("Arsenal")).toBeInTheDocument();
    expect(screen.queryByText("Real Madrid")).toBeNull();
    expect(screen.queryByRole("button", { name: "La Liga" })).toBeNull();
    expect(screen.queryByText(/LALIGA/)).toBeNull();
    expect(screen.getByRole("button", { name: "Following 0" })).toBeInTheDocument();
  });

  it("keeps league management available when every league is hidden", async () => {
    apiMocks.getCompetitionVisibility.mockResolvedValue({
      hidden_competitions: competitions.map(({ competition }) => competition),
    });
    const view = renderTeamsView("token");

    expect(await screen.findByText("No leagues are currently shown.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Leagues" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Choose leagues" }));
    expect(view.onManageLeagues).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Following 0" })).toBeInTheDocument();
  });

  it("shows FBS teams in one directory and filters them by conference", async () => {
    apiMocks.listTeams.mockResolvedValue([...teams, ...fbsTeams]);
    apiMocks.listCompetitions.mockResolvedValue([...competitions, fbsCompetition]);
    renderTeamsView(null);

    fireEvent.click(await screen.findByRole("button", { name: "College Football" }));

    const conference = screen.getByRole("combobox", { name: "Conference" });
    expect(conference).toHaveValue("all");
    expect(screen.queryByText("Conference", { exact: true })).toBeNull();
    expect(
      within(conference)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["All conferences", "Big Ten", "SEC"]);
    const directory = screen.getByRole("region", { name: "College Football" });
    expect(directory).toHaveTextContent("3 teams");
    expect(screen.getByText("Alabama Crimson Tide")).toBeInTheDocument();
    expect(screen.getByText("Auburn Tigers")).toBeInTheDocument();
    expect(screen.getByText("Michigan Wolverines")).toBeInTheDocument();
    expect(screen.getByText("ALA")).toBeInTheDocument();
    expect(screen.getByText("AUB")).toBeInTheDocument();
    expect(screen.queryByText(/FBS/)).toBeNull();

    fireEvent.change(conference, { target: { value: "Big Ten" } });
    expect(screen.getByRole("region", { name: "College Football" })).toHaveTextContent("1 team");
    expect(screen.getByText("Michigan Wolverines")).toBeInTheDocument();
    expect(screen.queryByText("Alabama Crimson Tide")).toBeNull();
  });

  it("sorts followed FBS teams first in the flat directory", async () => {
    apiMocks.listTeams.mockResolvedValue([...teams, ...fbsTeams]);
    apiMocks.listCompetitions.mockResolvedValue([...competitions, fbsCompetition]);
    apiMocks.listFollows.mockResolvedValue({ teams: [fbsTeams[0]], games: [] });
    renderTeamsView("token");

    fireEvent.click(await screen.findByRole("button", { name: "College Football" }));

    const directory = screen.getByRole("region", { name: "College Football" });
    expect(within(directory).getAllByRole("listitem")[0]).toHaveTextContent("Alabama Crimson Tide");
    expect(screen.queryByRole("region", { name: "Following" })).toBeNull();
  });

  it("returns to all teams if authentication disappears", async () => {
    apiMocks.listFollows.mockResolvedValue({ teams: [teams[1]], games: [] });
    const view = renderTeamsView("token");

    fireEvent.click(await screen.findByRole("button", { name: "Following 1" }));
    expect(screen.queryByText("Boston Celtics")).toBeNull();

    view.rerender(
      <QueryClientProvider client={view.client}>
        <TeamsView
          token={null}
          onSignInRequired={view.onSignInRequired}
          onManageLeagues={vi.fn()}
        />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.queryByRole("group", { name: "Team scope" })).toBeNull());
    expect(await screen.findByText("Boston Celtics")).toBeInTheDocument();
    expect(screen.getByText("New York Yankees")).toBeInTheDocument();
  });

  it("sorts followed teams first in the canonical directory and unfollows them", async () => {
    let followedTeams = [teams[0]];
    apiMocks.listFollows.mockImplementation(async () => ({ teams: followedTeams, games: [] }));
    apiMocks.unfollowTeam.mockImplementation(async () => {
      followedTeams = [];
      return { status: "ok" };
    });
    renderTeamsView("token");

    const directory = await screen.findByRole("region", { name: "All teams" });
    expect(within(directory).getAllByRole("listitem")[0]).toHaveTextContent("Boston Celtics");

    const followingAction = screen.getByRole("button", { name: /^Following$/ });
    expect(followingAction).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(followingAction);
    await waitFor(() => expect(apiMocks.unfollowTeam).toHaveBeenCalledWith("token", 2));
    await waitFor(() => expect(screen.getByRole("button", { name: "Following 0" })).toBeVisible());
    expect(within(directory).getAllByRole("listitem")[0]).toHaveTextContent("Arsenal");
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

    await waitFor(() => expect(apiMocks.followTeam).toHaveBeenCalledWith("token", 6));
    await waitFor(() => expect(screen.getByRole("button", { name: /^Following$/ })).toBeVisible());
    expect(screen.getByRole("button", { name: "Following 1" })).toBeVisible();
    expect(apiMocks.listFollows).toHaveBeenCalledTimes(2);
    expect(apiMocks.listTeams).toHaveBeenCalledTimes(1);
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(1);
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
