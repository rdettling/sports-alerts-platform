import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { type Game, type Team } from "../../../shared/api";
import { GameRowCard } from "./GameRowCard";

function makeTeam(id: number, abbreviation: string): Team {
  return {
    id,
    external_team_id: abbreviation,
    league: "NBA",
    name: abbreviation,
    abbreviation,
  };
}

function makeGame(overrides: Partial<Game> = {}): Game {
  return {
    id: 11,
    external_game_id: "ext-11",
    league: "NBA",
    home_team_id: 1,
    away_team_id: 2,
    scheduled_start_time: "2026-05-28T01:00:00Z",
    context_label: null,
    status: "scheduled",
    home_score: null,
    away_score: null,
    period: null,
    clock: null,
    is_final: false,
    last_ingested_at: null,
    odds: {
      market: "h2h",
      bookmaker: null,
      last_update: null,
      outcomes: [
        { outcome_key: "atl", outcome_label: "ATL", price_american: 105, team_side: "away" },
        { outcome_key: "bos", outcome_label: "BOS", price_american: -120, team_side: "home" },
      ],
    },
    ...overrides,
  };
}

describe("GameRowCard", () => {
  const home = makeTeam(1, "BOS");
  const away = makeTeam(2, "ATL");

  it("shows follow action for unfollowed non-final games", () => {
    const onFollow = vi.fn();
    render(
      <GameRowCard
        game={makeGame()}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
        onFollow={onFollow}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Follow" }));
    expect(onFollow).toHaveBeenCalledTimes(1);
  });

  it("shows alert settings and unfollow for followed non-final games", () => {
    const onUnfollow = vi.fn();
    const onOpenAlertSettings = vi.fn();
    render(
      <GameRowCard
        game={makeGame({ status: "scheduled", is_final: false })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed
        statusLabel="7:00 PM"
        onUnfollow={onUnfollow}
        onOpenAlertSettings={onOpenAlertSettings}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(screen.getByRole("button", { name: "Unfollow" }));

    expect(onOpenAlertSettings).toHaveBeenCalledTimes(1);
    expect(onUnfollow).toHaveBeenCalledTimes(1);
  });

  it("hides followed actions for final games", () => {
    render(
      <GameRowCard
        game={makeGame({ status: "final", is_final: true, home_score: 100, away_score: 95 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed
        statusLabel="Final"
      />,
    );

    expect(screen.queryByRole("button", { name: "Settings" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Unfollow" })).toBeNull();
  });

  it("does not show follow action for unfollowed final games", () => {
    render(
      <GameRowCard
        game={makeGame({ status: "final", is_final: true, home_score: 110, away_score: 108 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Final"
      />,
    );

    expect(screen.queryByRole("button", { name: "Follow" })).toBeNull();
  });

  it("shows context label when present", () => {
    render(
      <GameRowCard
        game={makeGame({ context_label: "NBA Finals - Game 5 · Knicks lead series 3-1" })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
        showContextLabel
      />,
    );

    expect(screen.getByText("NBA Finals - Game 5 · Knicks lead series 3-1")).toBeInTheDocument();
  });

  it("hides context label when not enabled for the surface", () => {
    render(
      <GameRowCard
        game={makeGame({ context_label: "Group Stage" })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.queryByText("Group Stage")).toBeNull();
  });

  it("shows draw odds for world cup pregame cards", () => {
    render(
      <GameRowCard
        game={makeGame({
          league: "WORLD_CUP",
          odds: {
            market: "h2h",
            bookmaker: null,
            last_update: null,
            outcomes: [
              { outcome_key: "mexico", outcome_label: "Mexico", price_american: 180, team_side: "away" },
              { outcome_key: "draw", outcome_label: "Draw", price_american: 210, team_side: null },
              { outcome_key: "united_states", outcome_label: "United States", price_american: 160, team_side: "home" },
            ],
          },
        })}
        sport="soccer"
        home={{ ...home, league: "WORLD_CUP" }}
        away={{ ...away, league: "WORLD_CUP" }}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByText("Draw")).toBeInTheDocument();
    expect(screen.getByText("+210")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "WC logo" })).toBeInTheDocument();
  });

  it("shows MLS draw odds and team and league logos", () => {
    render(
      <GameRowCard
        game={makeGame({
          league: "MLS",
          odds: {
            market: "h2h",
            bookmaker: null,
            last_update: null,
            outcomes: [
              { outcome_key: "los_angeles_fc", outcome_label: "Los Angeles FC", price_american: 180, team_side: "away" },
              { outcome_key: "draw", outcome_label: "Draw", price_american: 225, team_side: null },
              { outcome_key: "la_galaxy", outcome_label: "LA Galaxy", price_american: 150, team_side: "home" },
            ],
          },
        })}
        sport="soccer"
        home={{ ...home, external_team_id: "187", league: "MLS", abbreviation: "LA", name: "LA Galaxy" }}
        away={{ ...away, external_team_id: "18966", league: "MLS", abbreviation: "LAFC", name: "LAFC" }}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByText("Draw")).toBeInTheDocument();
    expect(screen.getByText("+225")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "MLS logo" })).toHaveAttribute(
      "src",
      "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg",
    );
    expect(screen.queryByText("MLS")).toBeNull();
    expect(screen.getByRole("img", { name: "LAFC logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/soccer/500/18966.png",
    );
  });

  it("shows WNBA two-way odds and league and team logos", () => {
    render(
      <GameRowCard
        game={makeGame({
          league: "WNBA",
          odds: {
            market: "h2h",
            bookmaker: null,
            last_update: null,
            outcomes: [
              { outcome_key: "las_vegas_aces", outcome_label: "Las Vegas Aces", price_american: 125, team_side: "away" },
              { outcome_key: "new_york_liberty", outcome_label: "New York Liberty", price_american: -145, team_side: "home" },
            ],
          },
        })}
        sport="basketball"
        home={{ ...home, external_team_id: "9", league: "WNBA", abbreviation: "NY", name: "New York Liberty" }}
        away={{ ...away, external_team_id: "17", league: "WNBA", abbreviation: "LV", name: "Las Vegas Aces" }}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.queryByText("Draw")).toBeNull();
    expect(screen.getByRole("img", { name: "WNBA logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png",
    );
    expect(screen.getByRole("img", { name: "Las Vegas Aces logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/wnba/500/lv.png",
    );
  });
});
