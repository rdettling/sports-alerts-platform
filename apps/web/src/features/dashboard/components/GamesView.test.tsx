import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
          league: "NBA",
          home_team_id: 10,
          away_team_id: 11,
          scheduled_start_time: "2026-06-12T20:00:00Z",
          context_label: null,
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
          league: "NBA",
          home_team_id: 12,
          away_team_id: 13,
          scheduled_start_time: "2026-06-13T20:00:00Z",
          context_label: null,
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
      follows: token ? {
        teams: [],
        games: [
          {
            id: 1,
            external_game_id: "today-game",
            league: "NBA",
            home_team_id: 10,
            away_team_id: 11,
            scheduled_start_time: "2026-06-12T20:00:00Z",
            context_label: null,
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
      } : { teams: [], games: [] },
      teams: [
        { id: 10, external_team_id: "10", league: "NBA", name: "Boston Celtics", abbreviation: "BOS" },
        { id: 11, external_team_id: "11", league: "NBA", name: "Atlanta Hawks", abbreviation: "ATL" },
        { id: 12, external_team_id: "12", league: "NBA", name: "Los Angeles Lakers", abbreviation: "LAL" },
        { id: 13, external_team_id: "13", league: "NBA", name: "New York Knicks", abbreviation: "NY" },
      ],
      leagues: [{ league: "NBA", sport: "basketball", label: "NBA", badge_label: "NBA", alert_types: ["game_start", "close_game_late", "final_result"], live_sync_interval_seconds: 120, default_test_matchup: ["ATL", "BOS"], is_enabled: true }],
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
    applyAlertOverride: vi.fn(async () => undefined),
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

  it("keeps all-days selected when the user clicks the all day filter", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());

    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByText("BOS")).toBeInTheDocument());
    expect(screen.queryByText("LAL")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "All days" }));

    await waitFor(() => expect(screen.getByText("LAL")).toBeInTheDocument());
    expect(screen.getByText("BOS")).toBeInTheDocument();
  });

  it("shows league sync status inside the filters rail", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T18:20:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByText("20m")).toBeInTheDocument());
    expect(screen.queryByText("Catalog sync 2m")).toBeNull();
  });

  it("filters to effective followed games for an authenticated user", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());
    render(<GamesView token="token" onSignInRequired={vi.fn()} />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: /Following 1/ }));
    expect(screen.getByText("BOS")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All days" }));
    expect(screen.queryByText("LAL")).toBeNull();
  });

  it("requests sign-in instead of following for a guest", async () => {
    const onSignInRequired = vi.fn();
    render(<GamesView token={null} onSignInRequired={onSignInRequired} />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "Follow" }));

    expect(onSignInRequired).toHaveBeenCalledTimes(1);
    expect(apiMocks.followGame).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Following/ })).toBeNull();
  });
});
