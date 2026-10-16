import { type ComponentProps } from "react";
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
    home_team_strength: { wins: 48, losses: 31, ties: 0, overtime_losses: null, rank: null },
    away_team_strength: { wins: 39, losses: 40, ties: 0, overtime_losses: null, rank: null },
    broadcast_names: [],
    possession_side: null,
    field_position: null,
    down_distance: null,
    outs: null,
    on_first: null,
    on_second: null,
    on_third: null,
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

const home = makeTeam(1, "BOS", "Boston Celtics");
const away = makeTeam(2, "ATL", "Atlanta Hawks");

function gameScoreRow(overrides: Partial<ComponentProps<typeof GameScoreRow>> = {}) {
  const props: ComponentProps<typeof GameScoreRow> = {
    game: makeGame(),
    sport: "basketball",
    home,
    away,
    isFollowed: false,
    statusLabel: "7:00 PM",
    ...overrides,
  };
  return <GameScoreRow {...props} />;
}

describe("GameScoreRow", () => {
  it.each([0, 1, 2])("shows baseball outs and runners: %s outs", (outs) => {
    const game = makeGame({
      competition: "MLB",
      status: "in_progress",
      clock: "Bot 7th",
      outs,
      on_first: true,
      on_second: false,
      on_third: true,
    });
    const { rerender } = render(gameScoreRow({ game, sport: "baseball", statusLabel: "Bot 7th" }));
    expect(screen.getByText(`${outs} ${outs === 1 ? "out" : "outs"}`)).toBeInTheDocument();
    const diamond = screen.getByRole("img", { name: "Runners on first and third" });
    expect(diamond.querySelectorAll(".occupied")).toHaveLength(2);
    expect(diamond.closest(".game-score-situation")).toContainElement(screen.getByText("Bot 7th"));
    fireEvent.click(screen.getByRole("button", { name: "Pregame odds" }));
    expect(screen.queryByRole("img", { name: /Runners on/ })).toBeNull();
    expect(screen.queryByText(/^[012] outs?$/)).toBeNull();
    expect(screen.getByText("Bot 7th")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pregame odds" }));
    rerender(
      gameScoreRow({
        game: { ...game, outs: null, on_first: false, on_third: false },
        sport: "baseball",
      }),
    );
    expect(
      screen.getByRole("img", { name: "Bases empty" }).querySelectorAll(".occupied"),
    ).toHaveLength(0);
    expect(screen.queryByText(/^[012] outs?$/)).toBeNull();
    rerender(gameScoreRow({ game: { ...game, on_second: null }, sport: "baseball" }));
    expect(screen.queryByRole("img", { name: /Runners on|Bases empty/ })).toBeNull();
  });

  it.each([
    { sport: "baseball" as const, status: "in_progress", clock: "Mid 7th", is_final: false },
    { sport: "baseball" as const, status: "in_progress", clock: "End 7th", is_final: false },
    { sport: "baseball" as const, status: "scheduled", clock: "Top 7th", is_final: false },
    { sport: "baseball" as const, status: "final", clock: "Bot 7th", is_final: true },
    { sport: "basketball" as const, status: "in_progress", clock: "Top 7th", is_final: false },
  ])("hides baseball details outside live half-innings: %o", ({ sport, ...state }) => {
    render(
      gameScoreRow({
        sport,
        game: makeGame({ ...state, outs: 2, on_first: true, on_second: true, on_third: true }),
      }),
    );
    expect(screen.queryByText("2 outs")).toBeNull();
    expect(screen.queryByRole("img", { name: /Runners on/ })).toBeNull();
  });

  it("omits an empty footer and places available actions in it", () => {
    const { container, rerender } = render(gameScoreRow());
    expect(container.querySelector("footer")).toBeNull();
    const onFollow = vi.fn();
    rerender(gameScoreRow({ onFollow }));
    expect(container.querySelector("footer")).toContainElement(
      screen.getByRole("button", { name: "Follow" }),
    );
    rerender(gameScoreRow({ isFollowed: true, actionsDisabled: true }));
    const footer = container.querySelector("footer")!;
    expect(within(footer).getByRole("button", { name: "Settings" })).toBeDisabled();
    expect(within(footer).getByRole("button", { name: "Unfollow" })).toBeDisabled();
    rerender(
      gameScoreRow({ game: makeGame({ status: "final", is_final: true }), isFollowed: true }),
    );
    expect(
      within(container.querySelector("footer")!).getByRole("button", { name: "Pregame odds" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unfollow" })).toBeNull();
  });

  it.each([
    { down: "2nd & 8", position: "UAB 16", expected: "2nd & 8 · UAB 16" },
    { down: "1st & Goal", position: "UAB 5", expected: "1st & Goal · UAB 5" },
    { down: null, position: "UAB 16", expected: "UAB 16" },
    { down: "3rd & 2", position: null, expected: "3rd & 2" },
  ])("shows available football situation text: $expected", ({ down, position, expected }) => {
    const game = makeGame({
      competition: "FBS",
      status: "in_progress",
      possession_side: "home",
      field_position: position,
      down_distance: down,
    });
    const { rerender } = render(gameScoreRow({ sport: "football", game }));
    expect(screen.getByText(expected).closest(".game-score-team")).toContainElement(
      screen.getByText("Boston Celtics"),
    );

    rerender(
      gameScoreRow({
        sport: "football",
        game: { ...game, down_distance: null, field_position: null },
      }),
    );
    expect(screen.queryByText(expected)).toBeNull();
    expect(screen.getByRole("img", { name: /has possession/ })).toBeInTheDocument();
  });

  it.each(["NFL", "FBS"] as const)("moves and clears live %s possession", (competition) => {
    const props = { sport: "football" as const };
    const game = makeGame({
      competition,
      status: "in_progress",
      possession_side: "home",
      field_position: "ODU 25",
    });
    const { rerender } = render(gameScoreRow({ ...props, game }));
    expect(screen.getByRole("img", { name: "Boston Celtics has possession" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Atlanta Hawks has possession" })).toBeNull();
    expect(screen.getByText("ODU 25").closest(".game-score-team")).toContainElement(
      screen.getByText("Boston Celtics"),
    );

    rerender(
      gameScoreRow({
        ...props,
        game: { ...game, possession_side: "away", field_position: "GASO 37" },
      }),
    );
    expect(screen.getByRole("img", { name: "Atlanta Hawks has possession" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Boston Celtics has possession" })).toBeNull();
    expect(screen.queryByText("ODU 25")).toBeNull();
    expect(screen.getByText("GASO 37").closest(".game-score-team")).toContainElement(
      screen.getByText("Atlanta Hawks"),
    );

    rerender(gameScoreRow({ ...props, game: { ...game, field_position: "ODU 40" } }));
    expect(screen.getByText("ODU 40")).toBeInTheDocument();
    expect(screen.queryByText("GASO 37")).toBeNull();

    rerender(gameScoreRow({ ...props, game: { ...game, field_position: null } }));
    expect(screen.queryByText("ODU 40")).toBeNull();
    expect(screen.getByRole("img", { name: /has possession/ })).toBeInTheDocument();

    rerender(gameScoreRow({ ...props, game: { ...game, possession_side: null } }));
    expect(screen.queryByText(/1st & 10/)).toBeNull();
    expect(screen.queryByText("ODU 25")).toBeNull();
    expect(screen.queryByRole("img", { name: /has possession/ })).toBeNull();
  });

  it.each([
    { sport: "football" as const, status: "scheduled", is_final: false },
    { sport: "football" as const, status: "postponed", is_final: false },
    { sport: "football" as const, status: "final", is_final: true },
    { sport: "football" as const, status: "in_progress", is_final: true },
    { sport: "basketball" as const, status: "in_progress", is_final: false },
  ])("hides possession outside live football: %o", ({ sport, status, is_final }) => {
    render(
      gameScoreRow({
        sport,
        game: makeGame({
          status,
          is_final,
          possession_side: "home",
          field_position: "ODU 25",
          down_distance: "1st & 10",
        }),
      }),
    );
    expect(screen.queryByText(/1st & 10/)).toBeNull();
    expect(screen.queryByText("ODU 25")).toBeNull();
    expect(screen.queryByRole("img", { name: /has possession/ })).toBeNull();
  });

  it("hides possession when viewing pregame odds", () => {
    render(
      gameScoreRow({
        sport: "football",
        game: makeGame({ status: "live", possession_side: "home", field_position: "ODU 25" }),
      }),
    );
    expect(screen.getByRole("img", { name: /has possession/ })).toBeInTheDocument();
    expect(screen.getByText("ODU 25")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pregame odds" }));
    expect(screen.queryByRole("img", { name: /has possession/ })).toBeNull();
    expect(screen.queryByText("ODU 25")).toBeNull();
  });

  it("shows full team names, records, raw odds, and competition identity", () => {
    render(gameScoreRow());

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
      gameScoreRow({
        game: makeGame({
          home_team_strength: {
            wins: null,
            losses: null,
            ties: null,
            overtime_losses: null,
            rank: null,
          },
          away_team_strength: {
            wins: null,
            losses: null,
            ties: null,
            overtime_losses: null,
            rank: null,
          },
        }),
      }),
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
      gameScoreRow({
        game: makeGame({
          competition: "FBS",
          home_team_strength: { wins: 8, losses: 1, ties: 0, overtime_losses: null, rank: 3 },
          away_team_strength: { wins: 6, losses: 3, ties: 0, overtime_losses: null, rank: null },
        }),
        sport: "football",
      }),
    );

    const homeName = screen.getByText("Boston Celtics");
    expect(homeName.parentElement).toHaveTextContent("#3Boston Celtics");
    expect(screen.getByText("#3")).toHaveClass("game-score-team-rank");
    expect(screen.queryByText("#6")).toBeNull();
  });

  it("shows follow action for unfollowed non-final games", () => {
    const onFollow = vi.fn();
    render(gameScoreRow({ onFollow }));

    fireEvent.click(screen.getByRole("button", { name: "Follow" }));
    expect(onFollow).toHaveBeenCalledTimes(1);
  });

  it("shows alert settings and unfollow for followed non-final games", () => {
    const onUnfollow = vi.fn();
    const onOpenAlertSettings = vi.fn();
    render(
      gameScoreRow({
        isFollowed: true,
        onUnfollow,
        onOpenAlertSettings,
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(screen.getByRole("button", { name: "Unfollow" }));
    expect(onOpenAlertSettings).toHaveBeenCalledTimes(1);
    expect(onUnfollow).toHaveBeenCalledTimes(1);
  });

  it("emphasizes the winner, de-emphasizes the loser, and hides final-game actions", () => {
    render(
      gameScoreRow({
        game: makeGame({ status: "final", is_final: true, home_score: 110, away_score: 108 }),
        isFollowed: true,
        statusLabel: "Final",
      }),
    );

    expect(screen.getByRole("listitem")).toHaveClass("final");
    expect(screen.getByText("Boston Celtics").closest(".game-score-team")).toHaveClass("winner");
    expect(screen.getByText("Atlanta Hawks").closest(".game-score-team")).toHaveClass("loser");
    expect(screen.queryByRole("button", { name: "Settings" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Unfollow" })).toBeNull();
  });

  it("marks live games and shows their score values", () => {
    render(
      gameScoreRow({
        game: makeGame({ status: "in_progress", home_score: 82, away_score: 79 }),
        statusLabel: "Q4 2:14",
      }),
    );

    expect(screen.getByRole("listitem")).toHaveClass("live");
    expect(screen.getByText("Q4 2:14")).toHaveClass("game-state-pill", "live");
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("79")).toBeInTheDocument();
  });

  it("toggles a live game between its score and pregame odds", () => {
    render(
      gameScoreRow({
        game: makeGame({ status: "in_progress", home_score: 82, away_score: 79 }),
        statusLabel: "Q4 2:14",
      }),
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
      gameScoreRow({
        game: makeGame({ status: "in_progress", home_score: 82, away_score: 79 }),
        statusLabel: "Q4 2:14",
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Pregame odds" }));
    rerender(
      gameScoreRow({
        game: makeGame({ status: "in_progress", home_score: 84, away_score: 81 }),
        statusLabel: "Q4 1:42",
      }),
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
      gameScoreRow({
        game: makeGame({ status: "final", is_final: true, home_score: 110, away_score: 108 }),
        statusLabel: "Final",
      }),
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
    render(gameScoreRow({ game, statusLabel: "Game status" }));

    expect(screen.queryByRole("button", { name: "Pregame odds" })).toBeNull();
  });

  it.each([
    ["live", makeGame({ status: "in_progress", home_score: 82, away_score: 79, odds: null })],
    [
      "final",
      makeGame({ status: "final", is_final: true, home_score: 110, away_score: 108, odds: null }),
    ],
  ])("shows placeholder odds for %s games without a snapshot", (_label, game) => {
    render(gameScoreRow({ game, statusLabel: "Game status" }));

    const toggle = screen.getByRole("button", { name: "Pregame odds" });
    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("marks postponed games and uses em dashes when no values exist", () => {
    render(
      gameScoreRow({
        game: makeGame({ status: "postponed", odds: null }),
        statusLabel: "Postponed",
      }),
    );

    expect(screen.getByRole("listitem")).toHaveClass("postponed");
    expect(screen.getByText("Postponed")).toHaveClass("game-state-pill", "postponed");
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("reveals the full context from its compact header disclosure", () => {
    const context = "NBA Finals - Game 5 · Knicks lead series 3-1";
    render(gameScoreRow({ game: makeGame({ context_label: context }) }));

    const summary = screen.getByLabelText(`Game context: ${context}`);
    const disclosure = summary.closest("details");

    expect(summary).toHaveAttribute("title", context);
    expect(disclosure).not.toHaveAttribute("open");
    fireEvent.click(summary);
    expect(disclosure).toHaveAttribute("open");
    expect(within(disclosure as HTMLElement).getAllByText(context)).toHaveLength(2);
  });

  it.each(["scheduled", "in_progress"])("shows broadcasts in the footer for %s games", (status) => {
    render(
      gameScoreRow({
        game: makeGame({
          status,
          broadcast_names: ["ESPN", "Peacock"],
        }),
        statusLabel: status === "scheduled" ? "7:00 PM" : "Q2 4:12",
      }),
    );

    const disclosure = screen.getByLabelText("Broadcasts: ESPN, Peacock");
    const footer = disclosure.closest("footer") as HTMLElement;
    expect(footer).not.toBeNull();
    const statusPill = screen.getByText(status === "scheduled" ? "7:00 PM" : "Q2 4:12");
    expect(statusPill).toHaveClass("game-state-pill");
    expect(footer).not.toContainElement(statusPill);
    if (status === "in_progress") {
      expect(within(footer).getByRole("button", { name: "Pregame odds" })).toBeInTheDocument();
    }
    expect(disclosure).toHaveAttribute("title", "ESPN, Peacock");
    expect(within(disclosure).getByText("ESPN")).toBeInTheDocument();
    expect(within(disclosure).getByText("+1")).toBeInTheDocument();
    expect(screen.getByText("Where to watch")).toBeInTheDocument();
  });

  it.each([
    ["final", true, "Final"],
    ["postponed", false, "Postponed"],
  ])("hides broadcasts for %s games", (status, isFinal, statusLabel) => {
    render(
      gameScoreRow({
        game: makeGame({
          status,
          is_final: isFinal,
          broadcast_names: ["ESPN", "Peacock"],
        }),
        statusLabel,
      }),
    );

    expect(screen.queryByLabelText("Broadcasts: ESPN, Peacock")).not.toBeInTheDocument();
    expect(screen.queryByText("ESPN")).not.toBeInTheDocument();
  });

  it("hides broadcast information when ESPN provides no names", () => {
    render(gameScoreRow());

    expect(screen.queryByText("ESPN, Peacock")).not.toBeInTheDocument();
  });

  it("keeps context separate from the primary broadcast disclosure", () => {
    render(
      gameScoreRow({
        game: makeGame({
          context_label: "NBA Finals - Game 5",
          broadcast_names: ["ESPN", "ABC"],
        }),
      }),
    );

    const context = screen.getByLabelText("Game context: NBA Finals - Game 5");
    expect(context.closest(".game-score-meta")).not.toBeNull();
    expect(
      screen.getByLabelText("Broadcasts: ESPN, ABC").closest(".game-score-footer-end"),
    ).not.toBeNull();
  });

  it("shows a single provider without a disclosure", () => {
    render(gameScoreRow({ game: makeGame({ broadcast_names: ["Peacock"] }) }));

    expect(screen.getByText("Peacock")).toHaveClass("game-broadcast-single");
    expect(screen.queryByText("Where to watch")).not.toBeInTheDocument();
  });

  it("shows three-way soccer odds", () => {
    render(
      gameScoreRow({
        game: makeGame({
          competition: "CHAMPIONS_LEAGUE",
          odds: {
            bookmaker: null,
            last_update: null,
            outcomes: [
              {
                outcome_key: "arsenal",
                outcome_label: "Arsenal",
                price_american: 180,
                team_side: "away",
              },
              { outcome_key: "draw", outcome_label: "Draw", price_american: 210, team_side: null },
              {
                outcome_key: "barcelona",
                outcome_label: "Barcelona",
                price_american: 160,
                team_side: "home",
              },
            ],
          },
        }),
        sport: "soccer",
        home: { ...home, sport: "soccer", competitions: ["CHAMPIONS_LEAGUE"] },
        away: { ...away, sport: "soccer", competitions: ["CHAMPIONS_LEAGUE"] },
      }),
    );

    expect(screen.getByText("Draw")).toBeInTheDocument();
    expect(screen.getByText("+210")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "UCL logo" })).toBeInTheDocument();
  });

  it("shows the draw outcome only while a started soccer game displays pregame odds", () => {
    render(
      gameScoreRow({
        game: makeGame({
          competition: "CHAMPIONS_LEAGUE",
          status: "in_progress",
          home_score: 1,
          away_score: 0,
          odds: {
            bookmaker: null,
            last_update: null,
            outcomes: [
              {
                outcome_key: "arsenal",
                outcome_label: "Arsenal",
                price_american: 180,
                team_side: "away",
              },
              { outcome_key: "draw", outcome_label: "Draw", price_american: 210, team_side: null },
              {
                outcome_key: "barcelona",
                outcome_label: "Barcelona",
                price_american: 160,
                team_side: "home",
              },
            ],
          },
        }),
        sport: "soccer",
        home: { ...home, sport: "soccer", competitions: ["CHAMPIONS_LEAGUE"] },
        away: { ...away, sport: "soccer", competitions: ["CHAMPIONS_LEAGUE"] },
        statusLabel: "2H 74′",
      }),
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
    render(gameScoreRow({ game: makeGame({ competition: "UNKNOWN" as Game["competition"] }) }));

    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });

  it("keeps MLS competition and team logo URLs", () => {
    render(
      gameScoreRow({
        game: makeGame({ competition: "MLS" }),
        sport: "soccer",
        home: {
          ...home,
          sport: "soccer",
          external_team_id: "187",
          competitions: ["MLS"],
          name: "LA Galaxy",
        },
        away: {
          ...away,
          external_team_id: "18966",
          sport: "soccer",
          competitions: ["MLS"],
          name: "LAFC",
          abbreviation: "LAFC",
        },
      }),
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
      gameScoreRow({
        game: makeGame({ competition: "LA_LIGA" }),
        sport: "soccer",
        home: {
          ...home,
          external_team_id: "83",
          sport: "soccer",
          competitions: ["LA_LIGA"],
          name: "Barcelona",
          abbreviation: "BAR",
        },
        away: {
          ...away,
          external_team_id: "86",
          sport: "soccer",
          competitions: ["LA_LIGA"],
          name: "Real Madrid",
          abbreviation: "RMA",
        },
        statusLabel: "12:00 PM",
      }),
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
      gameScoreRow({
        game: makeGame({ competition: "PREMIER_LEAGUE" }),
        sport: "soccer",
        home: {
          ...home,
          external_team_id: "359",
          sport: "soccer",
          competitions: ["PREMIER_LEAGUE"],
          name: "Arsenal",
          abbreviation: "ARS",
        },
        away: {
          ...away,
          external_team_id: "364",
          sport: "soccer",
          competitions: ["PREMIER_LEAGUE"],
          name: "Liverpool",
          abbreviation: "LIV",
        },
        statusLabel: "12:00 PM",
      }),
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
      gameScoreRow({
        game: makeGame({ competition: "NFL" }),
        sport: "football",
        home: {
          ...home,
          external_team_id: "2",
          sport: "football",
          competitions: ["NFL"],
          name: "Buffalo Bills",
          abbreviation: "BUF",
        },
        away: {
          ...away,
          external_team_id: "12",
          sport: "football",
          competitions: ["NFL"],
          name: "Kansas City Chiefs",
          abbreviation: "KC",
        },
        statusLabel: "5:20 PM",
      }),
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

  it("shows NHL records, identity, team logos, and two-way moneyline odds", () => {
    const bruins = {
      ...home,
      external_team_id: "1",
      sport: "hockey" as const,
      competitions: ["NHL" as const],
      name: "Boston Bruins",
      abbreviation: "BOS",
    };
    const sabres = {
      ...away,
      external_team_id: "2",
      sport: "hockey" as const,
      competitions: ["NHL" as const],
      name: "Buffalo Sabres",
      abbreviation: "BUF",
    };
    render(
      gameScoreRow({
        game: makeGame({
          competition: "NHL",
          home_team: bruins,
          away_team: sabres,
          home_team_strength: {
            wins: 40,
            losses: 25,
            ties: null,
            overtime_losses: 7,
            rank: null,
          },
          away_team_strength: {
            wins: 35,
            losses: 30,
            ties: null,
            overtime_losses: 7,
            rank: null,
          },
        }),
        sport: "hockey",
        home: bruins,
        away: sabres,
        statusLabel: "4:00 PM",
      }),
    );

    expect(screen.getByText("35-30-7")).toBeInTheDocument();
    expect(screen.getByText("40-25-7")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "NHL logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png",
    );
    expect(screen.getByRole("img", { name: "Buffalo Sabres logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/nhl/500/buf.png",
    );
    expect(screen.getByRole("img", { name: "Boston Bruins logo" })).toHaveAttribute(
      "src",
      "https://a.espncdn.com/i/teamlogos/nhl/500/bos.png",
    );
    expect(screen.getByText("+105")).toBeInTheDocument();
    expect(screen.getByText("-120")).toBeInTheDocument();
    expect(screen.queryByText("Draw")).not.toBeInTheDocument();
  });

  it("shows the FBS competition mark and team logos from the NCAA catalog", () => {
    render(
      gameScoreRow({
        game: makeGame({ competition: "FBS" }),
        sport: "football",
        home: {
          ...home,
          external_team_id: "333",
          sport: "football",
          competitions: ["FBS"],
          name: "Alabama Crimson Tide",
          abbreviation: "ALA",
        },
        away: {
          ...away,
          external_team_id: "2",
          sport: "football",
          competitions: ["FBS"],
          name: "Auburn Tigers",
          abbreviation: "AUB",
        },
        statusLabel: "4:30 PM",
      }),
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
