import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GamesView } from "./GamesView";

const apiMocks = vi.hoisted(() => ({
  followGame: vi.fn(async () => ({ status: "ok" })),
  unfollowGame: vi.fn(async () => ({ status: "ok" })),
}));

vi.mock("../../../shared/api", () => apiMocks);

vi.mock("../hooks/useGamesData", () => ({
  useGamesData: vi.fn((token: string | null) => ({
    isLoading: false,
    data: {
      games: [
        {
          id: 1,
          external_game_id: "today-game",
          competition: "NBA",
          home_team_id: 10,
          away_team_id: 11,
          scheduled_start_time: "2026-06-12T20:00:00Z",
          context_label: null,
          home_team_record: "48-31",
          away_team_record: "39-40",
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
          home_team_record: "55-24",
          away_team_record: "51-28",
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
          home_team_record: "24-13",
          away_team_record: "20-16",
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
          context_label: "Week 1",
          home_team_record: "0-0",
          away_team_record: "0-0",
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
          id: 5,
          external_game_id: "fbs-sec-game",
          competition: "FBS",
          home_team_id: 18,
          away_team_id: 19,
          scheduled_start_time: "2026-06-13T23:30:00Z",
          context_label: "Week 1",
          home_team_record: "0-0",
          away_team_record: "0-0",
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
                    home_team_record: "48-31",
                    away_team_record: "39-40",
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
          alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
          live_sync_interval_seconds: 120,
          is_enabled: true,
        },
      ],
    },
  })),
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
    render(<GamesView token={null} onSignInRequired={vi.fn()} />, { wrapper });

    expect(screen.getByRole("region", { name: "Games feed" })).toBeInTheDocument();
    expect(screen.queryByText(/Live scores and customizable/)).toBeNull();
  });

  it("selects today initially and supports selecting all dates", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());

    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByText("48-31")).toBeInTheDocument());
    expect(screen.queryByText("55-24")).toBeNull();
    expect(screen.getByRole("combobox", { name: "Game date" })).toHaveValue("2026-06-12");
    expect(screen.getByRole("option", { name: "Today (1)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "All dates (5)" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Game date" }), {
      target: { value: "all" },
    });

    await waitFor(() => expect(screen.getByText("55-24")).toBeInTheDocument());
    expect(screen.getByText("48-31")).toBeInTheDocument();
    expect(screen.getByText("20-16")).toBeInTheDocument();
  });

  it("moves between dates and disables navigation at boundaries", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

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

    fireEvent.change(screen.getByRole("combobox", { name: "Game date" }), {
      target: { value: "all" },
    });
    expect(screen.getByRole("button", { name: "Previous date" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next date" })).toBeDisabled();
  });

  it("filters by competition without showing sync telemetry", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T18:20:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "WNBA" }));

    await waitFor(() => expect(screen.getByText("20-16")).toBeInTheDocument());
    expect(screen.queryByText("48-31")).toBeNull();
    expect(screen.queryByText("20m")).toBeNull();
    expect(screen.getByRole("button", { name: "WNBA" })).toHaveAttribute("aria-pressed", "true");
  });

  it("filters FBS games when either team belongs to a conference", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-13T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "College Football" }));
    const conference = screen.getByRole("combobox", { name: "Conference" });
    expect(conference).toHaveValue("all");
    expect(screen.getByText("Alabama Crimson Tide")).toBeInTheDocument();
    expect(screen.getByText("Auburn Tigers")).toBeInTheDocument();

    fireEvent.change(conference, { target: { value: "Big Ten" } });

    expect(screen.getByText("Michigan Wolverines")).toBeInTheDocument();
    expect(screen.getByText("Alabama Crimson Tide")).toBeInTheDocument();
    expect(screen.queryByText("Auburn Tigers")).toBeNull();
    expect(screen.getByRole("option", { name: "All dates (1)" })).toBeInTheDocument();
  });

  it("filters to effective followed games for an authenticated user", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: /Following 1/ }));
    expect(screen.getByText("48-31")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Game date" }), {
      target: { value: "all" },
    });
    expect(screen.queryByText("55-24")).toBeNull();
    expect(screen.queryByText("20-16")).toBeNull();
  });

  it("requests sign-in instead of following for a guest", async () => {
    const onSignInRequired = vi.fn();
    render(<GamesView token={null} onSignInRequired={onSignInRequired} />, { wrapper });

    fireEvent.click((await screen.findAllByRole("button", { name: "Follow" }))[0]);

    expect(onSignInRequired).toHaveBeenCalledTimes(1);
    expect(apiMocks.followGame).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Following/ })).toBeNull();
  });

  it("refreshes only follows after changing a game follow", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <GamesView token="token" onSignInRequired={vi.fn()} />
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
    render(<GamesView token="empty-token" onSignInRequired={vi.fn()} />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "Following 0" }));

    expect(screen.getByText("No followed games match this filter.")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Game date" })).toHaveValue("all");
  });
});
