import { useState } from "react";

import { type Game, type GameTeam, type Sport, type Team } from "../../../shared/api";
import { CompetitionMark } from "../../../shared/components/CompetitionMark";
import { TeamLogo } from "../../../shared/components/TeamLogo";
import {
  drawOdds,
  formatMoneyline,
  formatTeamRecord,
  isThreeWayOdds,
  oddsOutcomeByTeamSide,
} from "./games/game-display";

type GameStateTone = "scheduled" | "live" | "final" | "postponed";

type GameScoreRowProps = {
  game: Game;
  sport: Sport;
  home: GameTeam | Team;
  away: GameTeam | Team;
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
  const [showPregameOdds, setShowPregameOdds] = useState(false);
  const hasScore = game.away_score !== null && game.home_score !== null;
  const isLive = game.status === "in_progress" || game.status === "live";
  const isFinal = game.status === "final" || game.is_final;
  const canTogglePregameOdds = isLive || isFinal;
  const isShowingPregameOdds = canTogglePregameOdds && showPregameOdds;
  const showScoreValues = (isLive || isFinal) && !isShowingPregameOdds;
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
  const broadcastText = game.broadcast_names.join(", ");
  const primaryBroadcast = game.broadcast_names[0];
  const additionalBroadcastCount = game.broadcast_names.length - 1;
  const showBroadcast = Boolean(primaryBroadcast) && (game.status === "scheduled" || isLive);
  const awayRecord = formatTeamRecord(game.away_team_strength, sport);
  const homeRecord = formatTeamRecord(game.home_team_strength, sport);
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
          <CompetitionMark competition={game.competition} className="game-score-competition-mark" />
          {game.context_label ? (
            <span className="game-score-context" title={game.context_label}>
              {game.context_label}
            </span>
          ) : null}
        </div>

        <div className="game-score-header-end">
          <div className="game-status-broadcast-group">
            {canTogglePregameOdds ? (
              <button
                className="game-score-action game-score-odds-toggle text-action"
                type="button"
                aria-pressed={isShowingPregameOdds}
                onClick={() => setShowPregameOdds((current) => !current)}
              >
                Pregame odds
              </button>
            ) : null}
            <span className={`game-state-pill ${statusTone}`}>{statusLabel}</span>
            {showBroadcast ? (
              <>
                <span className="game-broadcast-divider" aria-hidden>
                  ·
                </span>
                {additionalBroadcastCount > 0 ? (
                  <details className="game-broadcast-disclosure">
                    <summary title={broadcastText} aria-label={`Broadcasts: ${broadcastText}`}>
                      <span className="game-broadcast-primary">{primaryBroadcast}</span>
                      <span className="game-broadcast-count">+{additionalBroadcastCount}</span>
                    </summary>
                    <div className="game-broadcast-popover">
                      <strong>Where to watch</strong>
                      <ul>
                        {game.broadcast_names.map((name) => (
                          <li key={name}>{name}</li>
                        ))}
                      </ul>
                    </div>
                  </details>
                ) : (
                  <span className="game-broadcast-single" title={primaryBroadcast}>
                    {primaryBroadcast}
                  </span>
                )}
              </>
            ) : null}
          </div>
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
          <TeamLogo team={away} competition={game.competition} size={28} />
          <span className="game-score-team-copy">
            <strong title={away.name}>
              {game.away_team_strength.rank !== null ? (
                <span className="game-score-team-rank">#{game.away_team_strength.rank}</span>
              ) : null}
              <span className="game-score-team-name">{away.name}</span>
            </strong>
            {awayRecord ? <span>{awayRecord}</span> : null}
          </span>
          <span className="game-score-value">{awayValueText}</span>
        </div>
        <div className={`game-score-team ${homeWon ? "winner" : awayWon ? "loser" : ""}`.trim()}>
          <TeamLogo team={home} competition={game.competition} size={28} />
          <span className="game-score-team-copy">
            <strong title={home.name}>
              {game.home_team_strength.rank !== null ? (
                <span className="game-score-team-rank">#{game.home_team_strength.rank}</span>
              ) : null}
              <span className="game-score-team-name">{home.name}</span>
            </strong>
            {homeRecord ? <span>{homeRecord}</span> : null}
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
