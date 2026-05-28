import { type Game, type Team } from "../../../shared/api";
import { TeamLogo, formatMoneyline, leagueLogoUrl } from "../../../shared/lib/dashboard-ui";

type GameRowCardProps = {
  game: Game;
  home: Team;
  away: Team;
  isFollowed: boolean;
  statusLabel: string;
  actionsDisabled?: boolean;
  onFollow?: () => void;
  onUnfollow?: () => void;
  onOpenAlertSettings?: () => void;
};

export function GameRowCard({
  game,
  home,
  away,
  isFollowed,
  statusLabel,
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
  const awayValueText = showScoreValues
    ? String(game.away_score ?? "—")
    : game.odds
      ? formatMoneyline(game.odds.away_moneyline)
      : "—";
  const homeValueText = showScoreValues
    ? String(game.home_score ?? "—")
    : game.odds
      ? formatMoneyline(game.odds.home_moneyline)
      : "—";
  const league = (game.league || "N/A").toUpperCase();
  const logoUrl = leagueLogoUrl(game.league);
  const canFollow = !isFollowed && !isFinal && Boolean(onFollow);

  return (
    <article className="games-card-row" role="listitem">
      <div className="games-card-main">
        <div className="games-lines">
          <div className={`games-team-row ${awayWon ? "winner" : ""}`.trim()}>
            <div className="games-team-ident">
              <TeamLogo team={away} size={24} />
              <strong>{away.abbreviation}</strong>
            </div>
            <div className="games-team-score">{awayValueText}</div>
          </div>
          <div className={`games-team-row ${homeWon ? "winner" : ""}`.trim()}>
            <div className="games-team-ident">
              <TeamLogo team={home} size={24} />
              <strong>{home.abbreviation}</strong>
            </div>
            <div className="games-team-score">{homeValueText}</div>
          </div>
        </div>

        <div className="games-meta-rail">
          <div className="games-meta-col games-meta-col-logo">
            {logoUrl ? (
              <span className="games-league-logo-plain" aria-label={`${league} league`}>
                <img src={logoUrl} alt={`${league} logo`} className={`games-league-logo league-${(game.league || "").toLowerCase()}`.trim()} />
              </span>
            ) : (
              <span className="games-league-logo-fallback">{league}</span>
            )}
          </div>

          <div className="games-meta-col games-meta-col-status">
            <span className={`games-status-pill ${isLive ? "live" : isFinal ? "final" : "scheduled"}`.trim()}>
              {statusLabel}
            </span>
          </div>

          <div className="games-meta-col games-meta-col-actions">
            {isFollowed && !isFinal ? (
              <div className="following-game-actions following-game-actions-stacked">
                <button className="btn btn-secondary games-action-cell" type="button" onClick={onOpenAlertSettings} disabled={actionsDisabled || !onOpenAlertSettings}>
                  Alert settings
                </button>
                <button className="btn btn-secondary games-action-cell" type="button" onClick={onUnfollow} disabled={actionsDisabled || !onUnfollow}>
                  Unfollow
                </button>
              </div>
            ) : canFollow ? (
              <button className="btn games-action-cell games-action-cell-tall" type="button" disabled={actionsDisabled} onClick={onFollow}>
                Follow
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}
