import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GamesView } from "./GamesView";

const apiMocks = vi.hoisted(() => ({
  followGame: vi.fn(async () => ({ status: "ok" })),
  unfollowGame: vi.fn(async () => ({ status: "ok" })),
  updateCompetitionVisibility: vi.fn(async (_token: string, hidden_competitions: string[]) => ({
    hidden_competitions,
  })),
}));

vi.mock("../../../shared/api", () => apiMocks);

vi.mock("../hooks/useGamesData", () => ({
  useGamesData: vi.fn((token: string | null) => {
    const data = {
      games: [
        {
          id: 1,
          external_game_id: "today-game",
          competition: "NBA",
          home_team_id: 10,
          away_team_id: 11,
          scheduled_start_time: "2026-06-12T20:00:00Z",
          context_label: null,
          home_team_strength: { wins: 48, losses: 31, ties: 0, rank: null },
          away_team_strength: { wins: 39, losses: 40, ties: 0, rank: null },
          broadcast_names: [],
          status: "scheduled",
          home_score: null,
          away_score: null,
          period: null,
          clock: null,
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 2,
          external_game_id: "tomorrow-game",
          competition: "NBA",
          home_team_id: 12,
          away_team_id: 13,
          scheduled_start_time: "2026-06-13T20:00:00Z",
          context_label: null,
          home_team_strength: { wins: 55, losses: 24, ties: 0, rank: null },
          away_team_strength: { wins: 51, losses: 28, ties: 0, rank: null },
          broadcast_names: [],
          status: "scheduled",
          home_score: null,
          away_score: null,
          period: null,
          clock: null,
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 3,
          external_game_id: "tomorrow-wnba-game",
          competition: "WNBA",
          home_team_id: 14,
          away_team_id: 15,
          scheduled_start_time: "2026-06-13T22:00:00Z",
          context_label: null,
          home_team_strength: { wins: 24, losses: 13, ties: 0, rank: null },
          away_team_strength: { wins: 20, losses: 16, ties: 0, rank: null },
          broadcast_names: [],
          status: "scheduled",
          home_score: null,
          away_score: null,
          period: null,
          clock: null,
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 4,
          external_game_id: "fbs-cross-conference-game",
          competition: "FBS",
          home_team_id: 16,
          away_team_id: 17,
          scheduled_start_time: "2026-06-13T23:00:00Z",
          context_label: "Close late",
          home_team_strength: { wins: 0, losses: 0, ties: 0, rank: 5 },
          away_team_strength: { wins: 0, losses: 0, ties: 0, rank: null },
          broadcast_names: [],
          status: "in_progress",
          home_score: 24,
          away_score: 21,
          period: 4,
          clock: "02:00",
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 5,
          external_game_id: "fbs-sec-game",
          competition: "FBS",
          home_team_id: 18,
          away_team_id: 22,
          scheduled_start_time: "2026-06-13T23:30:00Z",
          context_label: "Tied early",
          home_team_strength: { wins: 0, losses: 0, ties: 0, rank: null },
          away_team_strength: { wins: 0, losses: 0, ties: 0, rank: null },
          broadcast_names: [],
          status: "in_progress",
          home_score: 0,
          away_score: 0,
          period: 1,
          clock: "15:00",
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 6,
          external_game_id: "fbs-late-blowout",
          competition: "FBS",
          home_team_id: 16,
          away_team_id: 18,
          scheduled_start_time: "2026-06-13T22:30:00Z",
          context_label: "Late blowout",
          home_team_strength: { wins: 0, losses: 0, ties: 0, rank: null },
          away_team_strength: { wins: 0, losses: 0, ties: 0, rank: null },
          broadcast_names: [],
          status: "in_progress",
          home_score: 35,
          away_score: 7,
          period: 4,
          clock: "01:00",
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 7,
          external_game_id: "fbs-upcoming",
          competition: "FBS",
          home_team_id: 18,
          away_team_id: 19,
          scheduled_start_time: "2026-06-13T23:40:00Z",
          context_label: "Upcoming",
          home_team_strength: { wins: 0, losses: 0, ties: 0, rank: null },
          away_team_strength: { wins: 0, losses: 0, ties: 0, rank: null },
          broadcast_names: [],
          status: "scheduled",
          home_score: null,
          away_score: null,
          period: null,
          clock: null,
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 8,
          external_game_id: "fbs-final",
          competition: "FBS",
          home_team_id: 16,
          away_team_id: 18,
          scheduled_start_time: "2026-06-13T22:00:00Z",
          context_label: "Final game",
          home_team_strength: { wins: 1, losses: 0, ties: 0, rank: null },
          away_team_strength: { wins: 0, losses: 1, ties: 0, rank: null },
          broadcast_names: [],
          status: "final",
          home_score: 28,
          away_score: 14,
          period: 4,
          clock: "00:00",
          is_final: true,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 9,
          external_game_id: "mlb-close-late",
          competition: "MLB",
          home_team_id: 20,
          away_team_id: 21,
          scheduled_start_time: "2026-06-13T20:00:00Z",
          context_label: "Baseball close late",
          home_team_strength: { wins: 40, losses: 30, ties: 0, rank: null },
          away_team_strength: { wins: 38, losses: 32, ties: 0, rank: null },
          broadcast_names: [],
          status: "in_progress",
          home_score: 4,
          away_score: 3,
          period: 8,
          clock: "Bottom 8th",
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 10,
          external_game_id: "mlb-tied-early",
          competition: "MLB",
          home_team_id: 20,
          away_team_id: 21,
          scheduled_start_time: "2026-06-13T20:30:00Z",
          context_label: "Baseball tied early",
          home_team_strength: { wins: 40, losses: 30, ties: 0, rank: null },
          away_team_strength: { wins: 38, losses: 32, ties: 0, rank: null },
          broadcast_names: [],
          status: "in_progress",
          home_score: 1,
          away_score: 1,
          period: 3,
          clock: "Top 3rd",
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
        {
          id: 11,
          external_game_id: "mlb-late-blowout",
          competition: "MLB",
          home_team_id: 20,
          away_team_id: 21,
          scheduled_start_time: "2026-06-13T19:30:00Z",
          context_label: "Baseball late blowout",
          home_team_strength: { wins: 40, losses: 30, ties: 0, rank: null },
          away_team_strength: { wins: 38, losses: 32, ties: 0, rank: null },
          broadcast_names: [],
          status: "in_progress",
          home_score: 8,
          away_score: 2,
          period: 9,
          clock: "Bottom 9th",
          is_final: false,
          last_ingested_at: "2026-06-12T18:00:00Z",
          odds: null,
        },
      ],
      follows:
        token === "empty-token"
          ? { teams: [], games: [] }
          : token
            ? {
                teams: [],
                games: [
                  {
                    id: 1,
                    external_game_id: "today-game",
                    competition: "NBA",
                    home_team_id: 10,
                    away_team_id: 11,
                    scheduled_start_time: "2026-06-12T20:00:00Z",
                    context_label: null,
                    home_team_strength: { wins: 48, losses: 31, ties: 0, rank: null },
                    away_team_strength: { wins: 39, losses: 40, ties: 0, rank: null },
                    broadcast_names: [],
                    status: "scheduled",
                    home_score: null,
                    away_score: null,
                    period: null,
                    clock: null,
                    is_final: false,
                    last_ingested_at: "2026-06-12T18:00:00Z",
                    odds: null,
                  },
                ],
              }
            : { teams: [], games: [] },
      teams: [
        {
          id: 10,
          external_team_id: "10",
          sport: "basketball",
          competitions: ["NBA"],
          name: "Boston Celtics",
          abbreviation: "BOS",
        },
        {
          id: 11,
          external_team_id: "11",
          sport: "basketball",
          competitions: ["NBA"],
          name: "Atlanta Hawks",
          abbreviation: "ATL",
        },
        {
          id: 12,
          external_team_id: "12",
          sport: "basketball",
          competitions: ["NBA"],
          name: "Los Angeles Lakers",
          abbreviation: "LAL",
        },
        {
          id: 13,
          external_team_id: "13",
          sport: "basketball",
          competitions: ["NBA"],
          name: "New York Knicks",
          abbreviation: "NY",
        },
        {
          id: 14,
          external_team_id: "14",
          sport: "basketball",
          competitions: ["WNBA"],
          name: "Las Vegas Aces",
          abbreviation: "LV",
        },
        {
          id: 15,
          external_team_id: "15",
          sport: "basketball",
          competitions: ["WNBA"],
          name: "Seattle Storm",
          abbreviation: "SEA",
        },
        {
          id: 16,
          external_team_id: "333",
          sport: "football",
          competitions: ["FBS"],
          conference: "SEC",
          name: "Alabama Crimson Tide",
          abbreviation: "ALA",
        },
        {
          id: 17,
          external_team_id: "130",
          sport: "football",
          competitions: ["FBS"],
          conference: "Big Ten",
          name: "Michigan Wolverines",
          abbreviation: "MICH",
        },
        {
          id: 18,
          external_team_id: "2",
          sport: "football",
          competitions: ["FBS"],
          conference: "SEC",
          name: "Auburn Tigers",
          abbreviation: "AUB",
        },
        {
          id: 19,
          external_team_id: "61",
          sport: "football",
          competitions: ["FBS"],
          conference: "SEC",
          name: "Georgia Bulldogs",
          abbreviation: "UGA",
        },
        {
          id: 20,
          external_team_id: "147",
          sport: "baseball",
          competitions: ["MLB"],
          conference: null,
          name: "New York Yankees",
          abbreviation: "NYY",
        },
        {
          id: 21,
          external_team_id: "111",
          sport: "baseball",
          competitions: ["MLB"],
          conference: null,
          name: "Boston Red Sox",
          abbreviation: "BOS",
        },
        {
          id: 22,
          external_team_id: "999999",
          sport: "football",
          competitions: [],
          conference: null,
          name: "Example State Bears",
          abbreviation: "EXST",
        },
      ],
      competitions: [
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
          competition: "WNBA",
          sport: "basketball",
          label: "WNBA",
          badge_label: "WNBA",
          alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
          live_sync_interval_seconds: 120,
          is_enabled: true,
        },
        {
          competition: "FBS",
          sport: "football",
          label: "College Football",
          badge_label: "FBS",
          alert_types: [
            "game_start",
            "close_game_late",
            "overtime_start",
            "score_changed",
            "lead_change",
            "final_result",
          ],
          live_sync_interval_seconds: 60,
          is_enabled: true,
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
      ].filter(({ competition }) => token !== "inactive-wnba-token" || competition !== "WNBA"),
      competitionVisibility:
        token === "hidden-wnba-token"
          ? { hidden_competitions: ["WNBA"] }
          : token === "all-hidden-token"
            ? { hidden_competitions: ["NBA", "WNBA", "FBS", "MLB"] }
            : { hidden_competitions: [] },
    };
    const teamsById = new Map(data.teams.map((team) => [team.id, team]));
    const participant = (teamId: number) => {
      const team = teamsById.get(teamId)!;
      return {
        id: team.id,
        external_team_id: team.external_team_id,
        sport: team.sport,
        conference: team.conference ?? null,
        name: team.name,
        abbreviation: team.abbreviation,
      };
    };
    const withParticipants = <T extends { home_team_id: number; away_team_id: number }>(
      game: T,
    ) => ({
      ...game,
      home_team: participant(game.home_team_id),
      away_team: participant(game.away_team_id),
    });
    return {
      isLoading: false,
      data: {
        ...data,
        games: data.games.map(withParticipants),
        follows: { ...data.follows, games: data.follows.games.map(withParticipants) },
      },
    };
  }),
}));

vi.mock("../hooks/useGameAlertSettings", () => ({
  useGameAlertSettings: vi.fn(() => ({
    alertGame: null,
    gameAlertState: null,
    alertsBusy: false,
    openGameAlerts: vi.fn(async () => undefined),
    closeGameAlerts: vi.fn(),
    updateGameAlertSettings: vi.fn(async () => undefined),
    resetGameAlertSettings: vi.fn(async () => undefined),
  })),
}));

vi.mock("./GameAlertSettingsModal", () => ({
  GameAlertSettingsModal: () => null,
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("GamesView", () => {
  beforeEach(() => {
    apiMocks.followGame.mockClear();
    apiMocks.unfollowGame.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders an accessible games feed without the removed marketing intro", () => {
    render(<GamesView token={null} onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    expect(screen.getByRole("region", { name: "Games feed" })).toBeInTheDocument();
    expect(screen.queryByText(/Live scores and customizable/)).toBeNull();
  });

  it("selects today initially without offering an all-dates option", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());

    render(<GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    await waitFor(() => expect(screen.getByText("48-31")).toBeInTheDocument());
    expect(screen.queryByText("55-24")).toBeNull();
    expect(screen.getByRole("combobox", { name: "Game date" })).toHaveValue("2026-06-12");
    expect(screen.getByRole("option", { name: "Today (1)" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /All dates/ })).toBeNull();
  });

  it("moves between dates and disables navigation at boundaries", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Game date" })).toHaveValue("2026-06-12"),
    );
    expect(screen.getByRole("button", { name: "Previous date" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Next date" }));

    expect(screen.getByRole("combobox", { name: "Game date" })).toHaveValue("2026-06-13");
    expect(screen.queryByText("48-31")).toBeNull();
    expect(screen.getByText("55-24")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next date" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Previous date" }));
    expect(screen.getByText("48-31")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous date" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next date" })).toBeEnabled();
  });

  it("filters by competition without showing sync telemetry", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T18:20:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    fireEvent.click(await screen.findByRole("button", { name: "WNBA" }));

    await waitFor(() => expect(screen.getByText("20-16")).toBeInTheDocument());
    expect(screen.queryByText("48-31")).toBeNull();
    expect(screen.queryByText("20m")).toBeNull();
    expect(screen.getByRole("button", { name: "WNBA" })).toHaveAttribute("aria-pressed", "true");
  });

  it("filters FBS games when either team belongs to a conference", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-13T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    fireEvent.click(await screen.findByRole("button", { name: "College Football" }));
    const conference = screen.getByRole("combobox", { name: "Conference" });
    expect(conference).toHaveValue("all");
    expect(
      within(conference)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["All conferences", "Top 25", "Big Ten", "SEC"]);
    expect(screen.getAllByText("Alabama Crimson Tide").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Auburn Tigers").length).toBeGreaterThan(0);
    expect(screen.getByText("Example State Bears")).toBeInTheDocument();

    fireEvent.change(conference, { target: { value: "Top 25" } });

    expect(screen.getByText("Alabama Crimson Tide")).toBeInTheDocument();
    expect(screen.getByText("Michigan Wolverines")).toBeInTheDocument();
    expect(screen.queryByText("Auburn Tigers")).toBeNull();

    fireEvent.change(conference, { target: { value: "Big Ten" } });

    expect(screen.getByText("Michigan Wolverines")).toBeInTheDocument();
    expect(screen.getByText("Alabama Crimson Tide")).toBeInTheDocument();
    expect(screen.queryByText("Auburn Tigers")).toBeNull();
    expect(screen.getByRole("option", { name: "Today (1)" })).toBeInTheDocument();
  });

  it("defaults to live first and retains sorting across competition filters", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-13T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    const sort = await screen.findByRole("combobox", { name: "Game sort" });
    expect(sort).toHaveValue("live_first");
    fireEvent.click(await screen.findByRole("button", { name: "College Football" }));

    const cardOrder = () =>
      screen
        .getAllByRole("listitem")
        .map((item) => item.querySelector(".game-score-context")?.textContent);

    expect(sort).toHaveValue("live_first");
    expect(cardOrder()).toEqual([
      "Close late",
      "Tied early",
      "Late blowout",
      "Upcoming",
      "Final game",
    ]);

    fireEvent.change(sort, { target: { value: "start_time" } });
    expect(cardOrder()).toEqual([
      "Final game",
      "Late blowout",
      "Close late",
      "Tied early",
      "Upcoming",
    ]);

    fireEvent.change(screen.getByRole("combobox", { name: "Conference" }), {
      target: { value: "SEC" },
    });
    expect(screen.getByRole("combobox", { name: "Game sort" })).toHaveValue("start_time");
    fireEvent.change(screen.getByRole("combobox", { name: "Conference" }), {
      target: { value: "all" },
    });

    fireEvent.change(sort, { target: { value: "ending_soon" } });
    expect(cardOrder()).toEqual([
      "Late blowout",
      "Close late",
      "Tied early",
      "Upcoming",
      "Final game",
    ]);

    fireEvent.click(screen.getByRole("button", { name: "WNBA" }));
    expect(screen.getByRole("combobox", { name: "Game sort" })).toHaveValue("ending_soon");

    fireEvent.click(screen.getByRole("button", { name: "NBA" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous date" }));
    expect(screen.getByRole("combobox", { name: "Game sort" })).toHaveValue("ending_soon");

    fireEvent.click(screen.getByRole("button", { name: "All competitions" }));
    expect(screen.getByRole("combobox", { name: "Game sort" })).toHaveValue("ending_soon");
    fireEvent.click(screen.getByRole("button", { name: "College Football" }));
    expect(screen.getByRole("combobox", { name: "Game sort" })).toHaveValue("ending_soon");
  });

  it("offers MLB sorting by inning progress and baseball watchability", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-13T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    fireEvent.click(await screen.findByRole("button", { name: "MLB" }));
    const sort = screen.getByRole("combobox", { name: "Game sort" });
    const cardOrder = () =>
      screen
        .getAllByRole("listitem")
        .map((item) => item.querySelector(".game-score-context")?.textContent);

    expect(sort).toHaveValue("live_first");
    expect(cardOrder()).toEqual([
      "Baseball close late",
      "Baseball tied early",
      "Baseball late blowout",
    ]);

    fireEvent.change(sort, { target: { value: "start_time" } });
    expect(cardOrder()).toEqual([
      "Baseball late blowout",
      "Baseball close late",
      "Baseball tied early",
    ]);

    fireEvent.change(sort, { target: { value: "ending_soon" } });
    expect(cardOrder()).toEqual([
      "Baseball late blowout",
      "Baseball close late",
      "Baseball tied early",
    ]);
  });

  it("filters to effective followed games for an authenticated user", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    fireEvent.click(await screen.findByRole("button", { name: /Following 1/ }));
    expect(screen.getByText("48-31")).toBeInTheDocument();
    expect(screen.queryByText("55-24")).toBeNull();
    expect(screen.queryByText("20-16")).toBeNull();
  });

  it("removes hidden competitions from tabs, games, and date counts", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-13T12:00:00Z").getTime());
    render(
      <GamesView token="hidden-wnba-token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />,
      { wrapper },
    );

    await screen.findByRole("button", { name: "All competitions" });
    expect(screen.queryByRole("button", { name: "Leagues" })).toBeNull();
    expect(screen.queryByRole("button", { name: "WNBA" })).toBeNull();
    expect(screen.queryByText("Las Vegas Aces")).toBeNull();
    expect(screen.getByRole("option", { name: "Today (9)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Following 1" })).toBeInTheDocument();
  });

  it("removes cached games when their competition becomes inactive", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-13T12:00:00Z").getTime());
    render(
      <GamesView
        token="inactive-wnba-token"
        onSignInRequired={vi.fn()}
        onManageLeagues={vi.fn()}
      />,
      { wrapper },
    );

    await screen.findByRole("button", { name: "All competitions" });
    expect(screen.queryByRole("button", { name: "Leagues" })).toBeNull();
    expect(screen.queryByRole("button", { name: "WNBA" })).toBeNull();
    expect(screen.queryByText("Las Vegas Aces")).toBeNull();
    expect(screen.getByRole("option", { name: "Today (9)" })).toBeInTheDocument();
  });

  it("keeps league management available when every league is hidden", async () => {
    const onManageLeagues = vi.fn();
    render(
      <GamesView
        token="all-hidden-token"
        onSignInRequired={vi.fn()}
        onManageLeagues={onManageLeagues}
      />,
      { wrapper },
    );

    expect(await screen.findByText("No leagues are currently shown.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Following 0" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Choose leagues" }));
    expect(onManageLeagues).toHaveBeenCalledTimes(1);
  });

  it("requests sign-in instead of following for a guest", async () => {
    const onSignInRequired = vi.fn();
    render(
      <GamesView token={null} onSignInRequired={onSignInRequired} onManageLeagues={vi.fn()} />,
      { wrapper },
    );

    fireEvent.click((await screen.findAllByRole("button", { name: "Follow" }))[0]);

    expect(onSignInRequired).toHaveBeenCalledTimes(1);
    expect(apiMocks.followGame).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Following/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Leagues" })).toBeNull();
  });

  it("refreshes only follows after changing a game follow", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <GamesView token="token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Unfollow" }));

    await waitFor(() => expect(apiMocks.unfollowGame).toHaveBeenCalledWith("token", 1));
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["follows", "token"] }),
    );
    expect(invalidate).toHaveBeenCalledTimes(1);
  });

  it("shows the followed-games empty state", async () => {
    render(<GamesView token="empty-token" onSignInRequired={vi.fn()} onManageLeagues={vi.fn()} />, {
      wrapper,
    });

    fireEvent.click(await screen.findByRole("button", { name: "Following 0" }));

    expect(screen.getByText("No followed games match this filter.")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Game date" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Game date" })).toHaveValue("");
    expect(screen.getByRole("option", { name: "No dates" })).toBeInTheDocument();
  });
});
