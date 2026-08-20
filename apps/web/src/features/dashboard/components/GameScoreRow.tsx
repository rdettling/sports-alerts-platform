import { type Game, type Sport, type Team } from "../../../shared/api";
import { TeamLogo } from "../../../shared/components/TeamLogo";
import { competitionBadgeLabel, competitionLogoUrl } from "../../../shared/lib/dashboard-ui";
import {
  drawOdds,
  formatMoneyline,
  isThreeWayOdds,
  oddsOutcomeByTeamSide,
} from "./games/game-display";

type GameStateTone = "scheduled" | "live" | "final" | "postponed";

type GameScoreRowProps = {
  game: Game;
  sport: Sport;
  home: Team;
  away: Team;
  isFollowed: boolean;
  statusLabel: string;
  actionsDisabled?: boolean;
  onFollow?: () => void;
  onUnfollow?: () => void;
  onOpenAlertSettings?: () => void;
};

export function GameScoreRow({
  game,
  sport,
  home,
  away,
  isFollowed,
  statusLabel,
  actionsDisabled = false,
  onFollow,
  onUnfollow,
  onOpenAlertSettings,
}: GameScoreRowProps) {
  const hasScore = game.away_score !== null && game.home_score !== null;
  const isLive = game.status === "in_progress" || game.status === "live";
  const isFinal = game.status === "final" || game.is_final;
  const showScoreValues = isLive || isFinal;
  const awayWon = Boolean(hasScore && isFinal && game.away_score! > game.home_score!);
  const homeWon = Boolean(hasScore && isFinal && game.home_score! > game.away_score!);
  const showThreeWayOdds = !showScoreValues && sport === "soccer" && isThreeWayOdds(game);
  const awayValueText = showScoreValues
    ? String(game.away_score ?? "—")
    : game.odds
      ? formatMoneyline(oddsOutcomeByTeamSide(game, "away"))
      : "—";
  const homeValueText = showScoreValues
    ? String(game.home_score ?? "—")
    : game.odds
      ? formatMoneyline(oddsOutcomeByTeamSide(game, "home"))
      : "—";
  const competition = competitionBadgeLabel(game.competition);
  const logoUrl = competitionLogoUrl(game.competition);
  const canFollow = !isFollowed && !isFinal && Boolean(onFollow);
  const statusTone: GameStateTone = isLive
    ? "live"
    : isFinal
      ? "final"
      : game.status === "postponed"
        ? "postponed"
        : "scheduled";

  return (
    <article
      className={`game-score-row ${statusTone}`}
      role="listitem"
      aria-label={`${away.name} at ${home.name}`}
    >
      <div className="game-score-header">
        <div className="game-score-meta">
          {logoUrl ? (
            <span className="game-score-competition-mark" aria-label={`${competition} competition`}>
              <img
                src={logoUrl}
                alt={`${competition} logo`}
                className={`game-score-competition-logo competition-${game.competition.toLowerCase()}`}
              />
            </span>
          ) : (
            <span className="game-score-competition-fallback">{competition}</span>
          )}
          {game.context_label ? (
            <span className="game-score-context" title={game.context_label}>
              {game.context_label}
            </span>
          ) : null}
        </div>

        <div className="game-score-header-end">
          <span className={`game-state-pill ${statusTone}`}>{statusLabel}</span>
          <div className="game-score-actions">
            {isFollowed && !isFinal ? (
              <>
                <button
                  className="game-score-action text-action"
                  type="button"
                  onClick={onOpenAlertSettings}
                  disabled={actionsDisabled || !onOpenAlertSettings}
                >
                  Settings
                </button>
                <button
                  className="game-score-action text-action"
                  type="button"
                  onClick={onUnfollow}
                  disabled={actionsDisabled || !onUnfollow}
                >
                  Unfollow
                </button>
              </>
            ) : canFollow ? (
              <button
                className="game-score-action text-action"
                type="button"
                disabled={actionsDisabled}
                onClick={onFollow}
              >
                Follow
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="game-score-matchup">
        <div className={`game-score-team ${awayWon ? "winner" : homeWon ? "loser" : ""}`.trim()}>
          <TeamLogo team={away} size={28} />
          <span className="game-score-team-copy">
            <strong title={away.name}>{away.name}</strong>
            <span>{away.abbreviation}</span>
          </span>
          <span className="game-score-value">{awayValueText}</span>
        </div>
        <div className={`game-score-team ${homeWon ? "winner" : awayWon ? "loser" : ""}`.trim()}>
          <TeamLogo team={home} size={28} />
          <span className="game-score-team-copy">
            <strong title={home.name}>{home.name}</strong>
            <span>{home.abbreviation}</span>
          </span>
          <span className="game-score-value">{homeValueText}</span>
        </div>
        {showThreeWayOdds ? (
          <div className="game-score-team game-score-draw" aria-label="Draw odds">
            <span className="game-score-logo-spacer" aria-hidden />
            <span className="game-score-team-copy">
              <strong>Draw</strong>
            </span>
            <span className="game-score-value">{formatMoneyline(drawOdds(game))}</span>
          </div>
        ) : null}
      </div>
    </article>
  );
}
