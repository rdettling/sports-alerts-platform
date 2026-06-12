import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GamesView } from "./GamesView";

vi.mock("../hooks/useGamesData", () => ({
  useGamesData: vi.fn(() => ({
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
      follows: { teams: [], games: [] },
      teams: [
        { id: 10, external_team_id: "10", league: "NBA", name: "Boston Celtics", abbreviation: "BOS" },
        { id: 11, external_team_id: "11", league: "NBA", name: "Atlanta Hawks", abbreviation: "ATL" },
        { id: 12, external_team_id: "12", league: "NBA", name: "Los Angeles Lakers", abbreviation: "LAL" },
        { id: 13, external_team_id: "13", league: "NBA", name: "New York Knicks", abbreviation: "NY" },
      ],
      leagues: [{ league: "NBA", label: "NBA", badge_label: "NBA", alert_types: ["game_start", "close_game_late", "final_result"], is_enabled: true }],
    },
  })),
}));

vi.mock("../hooks/useDashboardSyncItems", () => ({
  useDashboardSyncItems: vi.fn(() => [
    { key: "catalog", label: "Catalog", value: "2m ago", tone: "fresh" },
    { key: "nba", label: "NBA", value: "20m ago", tone: "stale" },
  ]),
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
  it("keeps all-days selected when the user clicks the all day filter", async () => {
    vi.spyOn(Date, "now").mockReturnValue(new Date("2026-06-12T12:00:00Z").getTime());

    render(<GamesView token="token" />, { wrapper });

    await waitFor(() => expect(screen.getByText("BOS")).toBeInTheDocument());
    expect(screen.queryByText("LAL")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "All days" }));

    await waitFor(() => expect(screen.getByText("LAL")).toBeInTheDocument());
    expect(screen.getByText("BOS")).toBeInTheDocument();
  });

  it("shows league sync status inside the filters rail", async () => {
    render(<GamesView token="token" />, { wrapper });

    await waitFor(() => expect(screen.getByText("20m")).toBeInTheDocument());
    expect(screen.queryByText("Catalog sync 2m")).toBeNull();
  });
});
