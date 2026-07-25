import { type Game, type Sport, type Team } from "../../../shared/api";
import {
  TeamLogo,
  drawOdds,
  formatMoneyline,
  isThreeWayOdds,
  leagueBadgeLabel,
  leagueLogoUrl,
  oddsOutcomeByTeamSide,
} from "../../../shared/lib/dashboard-ui";
import { GameStatePill, type GameStateTone } from "./GameStatePill";

type GameRowCardProps = {
  game: Game;
  sport: Sport;
  home: Team;
  away: Team;
  isFollowed: boolean;
  statusLabel: string;
  showContextLabel?: boolean;
  actionsDisabled?: boolean;
  onFollow?: () => void;
  onUnfollow?: () => void;
  onOpenAlertSettings?: () => void;
};

export function GameRowCard({
  game,
  sport,
  home,
  away,
  isFollowed,
  statusLabel,
  showContextLabel = false,
  actionsDisabled = false,
  onFollow,
  onUnfollow,
  onOpenAlertSettings,
}: GameRowCardProps) {
  const hasScore = game.away_score !== null && game.home_score !== null;
  const awayWon = Boolean(hasScore && game.is_final && game.away_score! > game.home_score!);
  const homeWon = Boolean(hasScore && game.is_final && game.home_score! > game.away_score!);
  const isLive = game.status === "in_progress" || game.status === "live";
  const isFinal = game.status === "final" || game.is_final;
  const showScoreValues = isLive || isFinal;
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
  const drawValueText = showThreeWayOdds ? formatMoneyline(drawOdds(game)) : null;
  const league = leagueBadgeLabel(game.league);
  const logoUrl = leagueLogoUrl(game.league);
  const canFollow = !isFollowed && !isFinal && Boolean(onFollow);
  const statusTone: GameStateTone = isLive
    ? "live"
    : isFinal
      ? "final"
      : game.status === "postponed"
        ? "postponed"
        : "scheduled";

  return (
    <article className="games-card-row" role="listitem">
      <div className="games-card-main">
        <div className="games-card-matchup">
          <div className="games-lines">
            <div className={`games-team-row ${awayWon ? "winner" : ""}`.trim()}>
              <div className="games-team-ident">
                <TeamLogo team={away} size={28} />
                <strong>{away.abbreviation}</strong>
              </div>
              <div className="games-team-score">{awayValueText}</div>
            </div>
            <div className={`games-team-row ${homeWon ? "winner" : ""}`.trim()}>
              <div className="games-team-ident">
                <TeamLogo team={home} size={28} />
                <strong>{home.abbreviation}</strong>
              </div>
              <div className="games-team-score">{homeValueText}</div>
            </div>
            {showThreeWayOdds ? (
              <div className="games-odds-draw-row" aria-label="Draw odds">
                <span className="games-odds-draw-label">Draw</span>
                <span className="games-team-score">{drawValueText}</span>
              </div>
            ) : null}
          </div>
          {showContextLabel && game.context_label ? (
            <div className="games-context-label">{game.context_label}</div>
          ) : null}
        </div>

        <div className="games-card-footer">
          <div className="games-card-meta">
            {logoUrl ? (
              <span className="games-league-logo-plain" aria-label={`${league} league`}>
                <img
                  src={logoUrl}
                  alt={`${league} logo`}
                  className={`games-league-logo league-${(game.league || "").toLowerCase()}`.trim()}
                />
              </span>
            ) : (
              <span className="games-league-logo-fallback">{league}</span>
            )}

            <GameStatePill text={statusLabel} tone={statusTone} />
          </div>

          <div className="games-card-actions">
            {isFollowed && !isFinal ? (
              <div className="games-follow-actions">
                <button
                  className="btn btn-secondary games-action-cell games-inline-action"
                  type="button"
                  onClick={onOpenAlertSettings}
                  disabled={actionsDisabled || !onOpenAlertSettings}
                >
                  Settings
                </button>
                <button
                  className="btn btn-secondary games-action-cell games-inline-action"
                  type="button"
                  onClick={onUnfollow}
                  disabled={actionsDisabled || !onUnfollow}
                >
                  Unfollow
                </button>
              </div>
            ) : canFollow ? (
              <button
                className="btn games-action-cell"
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
    </article>
  );
}
