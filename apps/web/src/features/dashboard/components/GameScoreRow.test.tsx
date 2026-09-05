import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { type Game, type Team } from "../../../shared/api";
import { GameScoreRow } from "./GameScoreRow";

function makeTeam(id: number, abbreviation: string, name: string): Team {
  return {
    id,
    external_team_id: abbreviation,
    sport: "basketball",
    competitions: ["NBA"],
    conference: null,
    name,
    abbreviation,
  };
}

function makeGame(overrides: Partial<Game> = {}): Game {
  return {
    id: 11,
    external_game_id: "ext-11",
    competition: "NBA",
    home_team_id: 1,
    away_team_id: 2,
    home_team: makeTeam(1, "BOS", "Boston Celtics"),
    away_team: makeTeam(2, "ATL", "Atlanta Hawks"),
    scheduled_start_time: "2026-05-28T01:00:00Z",
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
    last_ingested_at: null,
    odds: {
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

describe("GameScoreRow", () => {
  const home = makeTeam(1, "BOS", "Boston Celtics");
  const away = makeTeam(2, "ATL", "Atlanta Hawks");

  it("shows full team names, records, raw odds, and competition identity", () => {
    render(
      <GameScoreRow
        game={makeGame()}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByText("Atlanta Hawks")).toBeInTheDocument();
    expect(screen.getByText("Boston Celtics")).toBeInTheDocument();
    expect(screen.getByText("39-40")).toBeInTheDocument();
    expect(screen.getByText("48-31")).toBeInTheDocument();
    expect(screen.queryByText("ATL")).not.toBeInTheDocument();
    expect(screen.queryByText("BOS")).not.toBeInTheDocument();
    expect(screen.getByText("+105")).toBeInTheDocument();
    expect(screen.getByText("-120")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "NBA logo" })).toBeInTheDocument();
  });

  it("omits the secondary team line when records are unavailable", () => {
    render(
      <GameScoreRow
        game={makeGame({
          home_team_strength: { wins: null, losses: null, ties: null, rank: null },
          away_team_strength: { wins: null, losses: null, ties: null, rank: null },
        })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(
      screen
        .getByText("Atlanta Hawks")
        .closest(".game-score-team-copy")
        ?.querySelector(":scope > span"),
    ).toBeNull();
    expect(
      screen
        .getByText("Boston Celtics")
        .closest(".game-score-team-copy")
        ?.querySelector(":scope > span"),
    ).toBeNull();
  });

  it("shows an FBS poll rank immediately before the team name", () => {
    render(
      <GameScoreRow
        game={makeGame({
          competition: "FBS",
          home_team_strength: { wins: 8, losses: 1, ties: 0, rank: 3 },
          away_team_strength: { wins: 6, losses: 3, ties: 0, rank: null },
        })}
        sport="football"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    const homeName = screen.getByText("Boston Celtics");
    expect(homeName.parentElement).toHaveTextContent("#3Boston Celtics");
    expect(screen.getByText("#3")).toHaveClass("game-score-team-rank");
    expect(screen.queryByText("#6")).toBeNull();
  });

  it("shows follow action for unfollowed non-final games", () => {
    const onFollow = vi.fn();
    render(
      <GameScoreRow
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
      <GameScoreRow
        game={makeGame()}
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

  it("emphasizes the winner, de-emphasizes the loser, and hides final-game actions", () => {
    render(
      <GameScoreRow
        game={makeGame({ status: "final", is_final: true, home_score: 110, away_score: 108 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed
        statusLabel="Final"
      />,
    );

    expect(screen.getByRole("listitem")).toHaveClass("final");
    expect(screen.getByText("Boston Celtics").closest(".game-score-team")).toHaveClass("winner");
    expect(screen.getByText("Atlanta Hawks").closest(".game-score-team")).toHaveClass("loser");
    expect(screen.queryByRole("button", { name: "Settings" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Unfollow" })).toBeNull();
  });

  it("marks live games and shows their score values", () => {
    render(
      <GameScoreRow
        game={makeGame({ status: "in_progress", home_score: 82, away_score: 79 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Q4 2:14"
      />,
    );

    expect(screen.getByRole("listitem")).toHaveClass("live");
    expect(screen.getByText("Q4 2:14")).toHaveClass("game-state-pill", "live");
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("79")).toBeInTheDocument();
  });

  it("toggles a live game between its score and pregame odds", () => {
    render(
      <GameScoreRow
        game={makeGame({ status: "in_progress", home_score: 82, away_score: 79 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Q4 2:14"
      />,
    );

    const toggle = screen.getByRole("button", { name: "Pregame odds" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.queryByText("-120")).toBeNull();

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("82")).toBeNull();
    expect(screen.getByText("+105")).toBeInTheDocument();
    expect(screen.getByText("-120")).toBeInTheDocument();
    expect(screen.getByText("Q4 2:14")).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.queryByText("-120")).toBeNull();
  });

  it("preserves the selected odds view across live game updates", () => {
    const { rerender } = render(
      <GameScoreRow
        game={makeGame({ status: "in_progress", home_score: 82, away_score: 79 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Q4 2:14"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Pregame odds" }));
    rerender(
      <GameScoreRow
        game={makeGame({ status: "in_progress", home_score: 84, away_score: 81 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Q4 1:42"
      />,
    );

    expect(screen.getByRole("button", { name: "Pregame odds" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("+105")).toBeInTheDocument();
    expect(screen.queryByText("84")).toBeNull();
  });

  it("toggles final games while preserving winner and loser emphasis", () => {
    render(
      <GameScoreRow
        game={makeGame({ status: "final", is_final: true, home_score: 110, away_score: 108 })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Final"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Pregame odds" }));

    expect(screen.getByText("Boston Celtics").closest(".game-score-team")).toHaveClass("winner");
    expect(screen.getByText("Atlanta Hawks").closest(".game-score-team")).toHaveClass("loser");
    expect(screen.getByText("+105")).toBeInTheDocument();
    expect(screen.getByText("-120")).toBeInTheDocument();
    expect(screen.queryByText("110")).toBeNull();
  });

  it.each([
    ["scheduled", makeGame()],
    ["postponed", makeGame({ status: "postponed" })],
  ])("does not show the pregame toggle for %s games", (_label, game) => {
    render(
      <GameScoreRow
        game={game}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Game status"
      />,
    );

    expect(screen.queryByRole("button", { name: "Pregame odds" })).toBeNull();
  });

  it.each([
    ["live", makeGame({ status: "in_progress", home_score: 82, away_score: 79, odds: null })],
    [
      "final",
      makeGame({ status: "final", is_final: true, home_score: 110, away_score: 108, odds: null }),
    ],
  ])("shows placeholder odds for %s games without a snapshot", (_label, game) => {
    render(
      <GameScoreRow
        game={game}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Game status"
      />,
    );

    const toggle = screen.getByRole("button", { name: "Pregame odds" });
    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("marks postponed games and uses em dashes when no values exist", () => {
    render(
      <GameScoreRow
        game={makeGame({ status: "postponed", odds: null })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="Postponed"
      />,
    );

    expect(screen.getByRole("listitem")).toHaveClass("postponed");
    expect(screen.getByText("Postponed")).toHaveClass("game-state-pill", "postponed");
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("shows context text when present", () => {
    const context = "NBA Finals - Game 5 · Knicks lead series 3-1";
    render(
      <GameScoreRow
        game={makeGame({ context_label: context })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByText(context)).toHaveAttribute("title", context);
  });

  it.each(["scheduled", "in_progress"])(
    "shows broadcasts to the right of the status for %s games",
    (status) => {
      render(
        <GameScoreRow
          game={makeGame({
            status,
            broadcast_names: ["ESPN", "Peacock"],
          })}
          sport="basketball"
          home={home}
          away={away}
          isFollowed={false}
          statusLabel={status === "scheduled" ? "7:00 PM" : "Q2 4:12"}
        />,
      );

      const disclosure = screen.getByLabelText("Broadcasts: ESPN, Peacock");
      const group = disclosure.closest(".game-status-broadcast-group") as HTMLElement;
      expect(group).not.toBeNull();
      const statusPill = within(group).getByText(status === "scheduled" ? "7:00 PM" : "Q2 4:12");
      expect(statusPill).toHaveClass("game-state-pill");
      expect(statusPill.nextElementSibling).toHaveTextContent("·");
      expect(statusPill.nextElementSibling?.nextElementSibling).toBe(disclosure.closest("details"));
      if (status === "in_progress") {
        expect(within(group).getByRole("button", { name: "Pregame odds" }).nextElementSibling).toBe(
          statusPill,
        );
      }
      expect(disclosure).toHaveAttribute("title", "ESPN, Peacock");
      expect(within(disclosure).getByText("ESPN")).toBeInTheDocument();
      expect(within(disclosure).getByText("+1")).toBeInTheDocument();
      expect(screen.getByText("Where to watch")).toBeInTheDocument();
    },
  );

  it.each([
    ["final", true, "Final"],
    ["postponed", false, "Postponed"],
  ])("hides broadcasts for %s games", (status, isFinal, statusLabel) => {
    render(
      <GameScoreRow
        game={makeGame({
          status,
          is_final: isFinal,
          broadcast_names: ["ESPN", "Peacock"],
        })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel={statusLabel}
      />,
    );

    expect(screen.queryByLabelText("Broadcasts: ESPN, Peacock")).not.toBeInTheDocument();
    expect(screen.queryByText("ESPN")).not.toBeInTheDocument();
  });

  it("hides broadcast information when ESPN provides no names", () => {
    render(
      <GameScoreRow
        game={makeGame()}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.queryByText("ESPN, Peacock")).not.toBeInTheDocument();
  });

  it("keeps context separate from the primary broadcast disclosure", () => {
    render(
      <GameScoreRow
        game={makeGame({
          context_label: "NBA Finals - Game 5",
          broadcast_names: ["ESPN", "ABC"],
        })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    const context = screen.getByText("NBA Finals - Game 5");
    expect(context.closest(".game-score-meta")).not.toBeNull();
    expect(
      screen.getByLabelText("Broadcasts: ESPN, ABC").closest(".game-score-header-end"),
    ).not.toBeNull();
  });

  it("shows a single provider without a disclosure", () => {
    render(
      <GameScoreRow
        game={makeGame({ broadcast_names: ["Peacock"] })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByText("Peacock")).toHaveClass("game-broadcast-single");
    expect(screen.queryByText("Where to watch")).not.toBeInTheDocument();
  });

  it("shows three-way soccer odds", () => {
    render(
      <GameScoreRow
        game={makeGame({
          competition: "WORLD_CUP",
          odds: {
            bookmaker: null,
            last_update: null,
            outcomes: [
              {
                outcome_key: "mexico",
                outcome_label: "Mexico",
                price_american: 180,
                team_side: "away",
              },
              { outcome_key: "draw", outcome_label: "Draw", price_american: 210, team_side: null },
              {
                outcome_key: "usa",
                outcome_label: "United States",
                price_american: 160,
                team_side: "home",
              },
            ],
          },
        })}
        sport="soccer"
        home={{ ...home, sport: "soccer", competitions: ["WORLD_CUP"] }}
        away={{ ...away, sport: "soccer", competitions: ["WORLD_CUP"] }}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByText("Draw")).toBeInTheDocument();
    expect(screen.getByText("+210")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "WC logo" })).toBeInTheDocument();
  });

  it("shows the draw outcome only while a started soccer game displays pregame odds", () => {
    render(
      <GameScoreRow
        game={makeGame({
          competition: "WORLD_CUP",
          status: "in_progress",
          home_score: 1,
          away_score: 0,
          odds: {
            bookmaker: null,
            last_update: null,
            outcomes: [
              {
                outcome_key: "mexico",
                outcome_label: "Mexico",
                price_american: 180,
                team_side: "away",
              },
              { outcome_key: "draw", outcome_label: "Draw", price_american: 210, team_side: null },
              {
                outcome_key: "usa",
                outcome_label: "United States",
                price_american: 160,
                team_side: "home",
              },
            ],
          },
        })}
        sport="soccer"
        home={{ ...home, sport: "soccer", competitions: ["WORLD_CUP"] }}
        away={{ ...away, sport: "soccer", competitions: ["WORLD_CUP"] }}
        isFollowed={false}
        statusLabel="2H 74′"
      />,
    );

    expect(screen.queryByText("Draw")).toBeNull();

    const toggle = screen.getByRole("button", { name: "Pregame odds" });
    fireEvent.click(toggle);

    expect(screen.getByText("Draw")).toBeInTheDocument();
    expect(screen.getByText("+210")).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(screen.queryByText("Draw")).toBeNull();
  });

  it("uses a text fallback when a competition has no logo", () => {
    render(
      <GameScoreRow
        game={makeGame({ competition: "UNKNOWN" as Game["competition"] })}
        sport="basketball"
        home={home}
        away={away}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });

  it("keeps MLS competition and team logo URLs", () => {
    render(
      <GameScoreRow
        game={makeGame({ competition: "MLS" })}
        sport="soccer"
        home={{
          ...home,
          sport: "soccer",
          external_team_id: "187",
          competitions: ["MLS"],
          name: "LA Galaxy",
        }}
        away={{
          ...away,
          external_team_id: "18966",
          sport: "soccer",
          competitions: ["MLS"],
          name: "LAFC",
          abbreviation: "LAFC",
        }}
        isFollowed={false}
        statusLabel="7:00 PM"
      />,
    );

    expect(screen.getByRole("img", { name: "MLS logo" })).toHaveAttribute(
      "src",
      "https://upload.wikimedia.org/wikipedia/commons/c/c7/Major_League_Soccer_logo.svg",
    );
    expect(screen.getByRole("img", { name: "LAFC logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/soccer/500/18966.png",
    );
  });

  it("shows La Liga identity and club logo URLs", () => {
    render(
      <GameScoreRow
        game={makeGame({ competition: "LA_LIGA" })}
        sport="soccer"
        home={{
          ...home,
          external_team_id: "83",
          sport: "soccer",
          competitions: ["LA_LIGA"],
          name: "Barcelona",
          abbreviation: "BAR",
        }}
        away={{
          ...away,
          external_team_id: "86",
          sport: "soccer",
          competitions: ["LA_LIGA"],
          name: "Real Madrid",
          abbreviation: "RMA",
        }}
        isFollowed={false}
        statusLabel="12:00 PM"
      />,
    );

    expect(screen.getByRole("img", { name: "LALIGA logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/leaguelogos/soccer/500/15.png",
    );
    expect(screen.getByRole("img", { name: "Real Madrid logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/soccer/500/86.png",
    );
    expect(screen.getByRole("img", { name: "Barcelona logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/soccer/500/83.png",
    );
  });

  it("shows Premier League identity and club logo URLs", () => {
    render(
      <GameScoreRow
        game={makeGame({ competition: "PREMIER_LEAGUE" })}
        sport="soccer"
        home={{
          ...home,
          external_team_id: "359",
          sport: "soccer",
          competitions: ["PREMIER_LEAGUE"],
          name: "Arsenal",
          abbreviation: "ARS",
        }}
        away={{
          ...away,
          external_team_id: "364",
          sport: "soccer",
          competitions: ["PREMIER_LEAGUE"],
          name: "Liverpool",
          abbreviation: "LIV",
        }}
        isFollowed={false}
        statusLabel="12:00 PM"
      />,
    );

    expect(screen.getByRole("img", { name: "EPL logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/leaguelogos/soccer/500/23.png",
    );
    expect(screen.getByRole("img", { name: "Liverpool logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/soccer/500/364.png",
    );
    expect(screen.getByRole("img", { name: "Arsenal logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/soccer/500/359.png",
    );
  });

  it("shows NFL identity, team logos, and two-way moneyline odds", () => {
    render(
      <GameScoreRow
        game={makeGame({ competition: "NFL" })}
        sport="football"
        home={{
          ...home,
          external_team_id: "2",
          sport: "football",
          competitions: ["NFL"],
          name: "Buffalo Bills",
          abbreviation: "BUF",
        }}
        away={{
          ...away,
          external_team_id: "12",
          sport: "football",
          competitions: ["NFL"],
          name: "Kansas City Chiefs",
          abbreviation: "KC",
        }}
        isFollowed={false}
        statusLabel="5:20 PM"
      />,
    );

    expect(screen.getByRole("img", { name: "NFL logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png",
    );
    expect(screen.getByRole("img", { name: "Kansas City Chiefs logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
    );
    expect(screen.getByRole("img", { name: "Buffalo Bills logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
    );
    expect(screen.queryByText("Draw")).not.toBeInTheDocument();
  });

  it("shows the FBS competition mark and team logos from the NCAA catalog", () => {
    render(
      <GameScoreRow
        game={makeGame({ competition: "FBS" })}
        sport="football"
        home={{
          ...home,
          external_team_id: "333",
          sport: "football",
          competitions: ["FBS"],
          name: "Alabama Crimson Tide",
          abbreviation: "ALA",
        }}
        away={{
          ...away,
          external_team_id: "2",
          sport: "football",
          competitions: ["FBS"],
          name: "Auburn Tigers",
          abbreviation: "AUB",
        }}
        isFollowed={false}
        statusLabel="4:30 PM"
      />,
    );

    const competitionMark = screen.getByRole("img", { name: "FBS logo" });
    expect(competitionMark).not.toHaveTextContent("FBS");
    expect(competitionMark).toHaveAttribute(
      "src",
      "https://a.espncdn.com/redesign/assets/img/icons/ESPN-icon-football-college.png",
    );
    expect(screen.getByRole("img", { name: "Alabama Crimson Tide logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/ncaa/500/333.png",
    );
    expect(screen.getByRole("img", { name: "Auburn Tigers logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/ncaa/500/2.png",
    );
  });
});
