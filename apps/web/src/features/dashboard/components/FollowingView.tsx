import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  clearGameAlertOverride,
  followTeam,
  getGameAlertPreferences,
  unfollowGame,
  unfollowTeam,
  updateGameAlertOverride,
  type Game,
  type GameAlertPreferences,
  type Team,
} from "../../../shared/api";
import { PREFERENCE_LABELS, TeamLogo, formatGameTime, formatMoneyline, leagueLogoUrl, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";
import { useFollowingData } from "../hooks/useFollowingData";

function statusLabel(status: string, isFinal: boolean, fallbackTime: string): string {
  if (status === "in_progress" || status === "live") return `Live • ${fallbackTime}`;
  if (status === "final" || isFinal) return "Final";
  return fallbackTime;
}

export function FollowingView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();
  const queryClient = useQueryClient();
  const { data, isLoading, error: queryError } = useFollowingData(token);

  const [teamSearch, setTeamSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);
  const [alertGame, setAlertGame] = useState<Game | null>(null);
  const [gameAlertState, setGameAlertState] = useState<GameAlertPreferences | null>(null);
  const [alertsBusy, setAlertsBusy] = useState(false);

  const teams = data?.teams ?? [];
  const followedTeams = data?.follows.teams ?? [];
  const followedGames = data?.games ?? [];

  useEffect(() => {
    if (queryError) setError(messageFromUnknown(queryError));
  }, [queryError]);

  useEffect(() => {
    if (data) setLastSync(new Date());
  }, [data, setLastSync]);

  const followTeamMutation = useMutation({
    mutationFn: (teamId: number) => followTeam(token, teamId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["following-page", token] });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const unfollowTeamMutation = useMutation({
    mutationFn: (teamId: number) => unfollowTeam(token, teamId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["following-page", token] });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const unfollowGameMutation = useMutation({
    mutationFn: (gameId: number) => unfollowGame(token, gameId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["following-page", token] });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const teamMap = useMemo(() => new Map(teams.map((team: Team) => [team.id, team])), [teams]);
  const followedTeamIds = useMemo(() => new Set(followedTeams.map((team) => team.id)), [followedTeams]);

  const addableTeams = useMemo(() => {
    const q = teamSearch.trim().toLowerCase();
    return teams
      .filter((team) => !followedTeamIds.has(team.id))
      .filter((team) => !q || `${team.name} ${team.abbreviation}`.toLowerCase().includes(q))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [teams, followedTeamIds, teamSearch]);

  const openGameAlerts = async (game: Game) => {
    setError(null);
    setAlertGame(game);
    setAlertsBusy(true);
    try {
      const payload = await getGameAlertPreferences(token, game.id);
      setGameAlertState(payload);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
      setAlertGame(null);
    } finally {
      setAlertsBusy(false);
    }
  };

  const applyAlertOverride = async (
    gameId: number,
    alertType: string,
    payload: {
      is_enabled_override?: boolean | null;
      close_game_margin_threshold_override?: number | null;
      close_game_time_threshold_seconds_override?: number | null;
      inning_start_threshold_override?: number | null;
    },
  ) => {
    setAlertsBusy(true);
    setError(null);
    try {
      await updateGameAlertOverride(token, gameId, alertType, payload);
      const refreshed = await getGameAlertPreferences(token, gameId);
      setGameAlertState(refreshed);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setAlertsBusy(false);
    }
  };

  const clearAlertOverride = async (gameId: number, alertType: string) => {
    setAlertsBusy(true);
    setError(null);
    try {
      await clearGameAlertOverride(token, gameId, alertType);
      const refreshed = await getGameAlertPreferences(token, gameId);
      setGameAlertState(refreshed);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setAlertsBusy(false);
    }
  };

  return (
    <section className="view-stack following-simple-page">
      {error ? <p className="error">{error}</p> : null}
      {isLoading ? <p className="muted">Loading following...</p> : null}

      {!isLoading ? (
        <div className="following-two-col-panels">
          <section className="panel following-simple-section">
            <h4>Followed Teams ({followedTeams.length})</h4>
            <div className="following-team-autocomplete">
              <input
                type="search"
                placeholder="Type to find a team..."
                value={teamSearch}
                onChange={(event) => setTeamSearch(event.target.value)}
              />
              {teamSearch.trim().length > 0 ? (
                <div className="following-team-options">
                  {addableTeams.slice(0, 8).map((team) => (
                    <button
                      key={team.id}
                      type="button"
                      className="following-team-option"
                      disabled={followTeamMutation.isPending}
                      onClick={async () => {
                        await followTeamMutation.mutateAsync(team.id);
                        setTeamSearch("");
                      }}
                    >
                      <TeamLogo team={team} size={18} />
                      <span>{team.name} ({team.abbreviation})</span>
                    </button>
                  ))}
                  {addableTeams.length === 0 ? <p className="muted">No matching teams.</p> : null}
                </div>
              ) : null}
            </div>

            {followedTeams.length === 0 ? <p className="muted">No followed teams yet.</p> : null}
            <ul className="list following-simple-team-list">
              {followedTeams.map((team) => (
                <li key={team.id} className="row-card">
                  <span className="following-followed-team-main">
                    <TeamLogo team={team} size={22} />
                    <span className="following-followed-team-text">
                      <strong>{team.name}</strong>
                    </span>
                  </span>
                  <button
                    className="btn btn-secondary"
                    disabled={busyTeamId === team.id || unfollowTeamMutation.isPending}
                    onClick={async () => {
                      setBusyTeamId(team.id);
                      try {
                        await unfollowTeamMutation.mutateAsync(team.id);
                      } finally {
                        setBusyTeamId(null);
                      }
                    }}
                  >
                    Unfollow
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="panel following-simple-section">
            <h4>Followed Games ({followedGames.length})</h4>
            {followedGames.length === 0 ? <p className="muted">No followed games yet.</p> : null}
            <div className="games-cards">
              {followedGames.map((game) => {
                const home = teamMap.get(game.home_team_id);
                const away = teamMap.get(game.away_team_id);
                if (!home || !away) return null;
                const hasScore = game.away_score !== null && game.home_score !== null;
                const awayWon = Boolean(hasScore && game.is_final && game.away_score! > game.home_score!);
                const homeWon = Boolean(hasScore && game.is_final && game.home_score! > game.away_score!);
                const isLive = game.status === "in_progress" || game.status === "live";
                const isFinal = game.status === "final" || game.is_final;
                const showScoreValues = isLive || isFinal;
                const awayValueText = showScoreValues ? String(game.away_score ?? "—") : game.odds ? formatMoneyline(game.odds.away_moneyline) : "—";
                const homeValueText = showScoreValues ? String(game.home_score ?? "—") : game.odds ? formatMoneyline(game.odds.home_moneyline) : "—";

                return (
                  <article key={game.id} className="games-card-row" role="listitem">
                    <div className="games-card-main">
                      <div className="games-lines">
                        <div className={`games-team-row ${awayWon ? "winner" : ""}`.trim()}>
                          <div className="games-team-ident"><TeamLogo team={away} size={24} /><strong>{away.abbreviation}</strong></div>
                          <div className="games-team-score">{awayValueText}</div>
                        </div>
                        <div className={`games-team-row ${homeWon ? "winner" : ""}`.trim()}>
                          <div className="games-team-ident"><TeamLogo team={home} size={24} /><strong>{home.abbreviation}</strong></div>
                          <div className="games-team-score">{homeValueText}</div>
                        </div>
                      </div>

                      <div className="games-meta-rail">
                        {leagueLogoUrl(game.league) ? (
                          <span className="games-league-logo-wrap">
                            <img src={leagueLogoUrl(game.league) ?? ""} alt="League logo" className={`games-league-logo league-${(game.league || "").toLowerCase()}`.trim()} />
                          </span>
                        ) : null}
                        <span className={`games-status-pill ${isLive ? "live" : isFinal ? "final" : "scheduled"}`.trim()}>{statusLabel(game.status, isFinal, formatGameTime(game))}</span>
                        <div className="following-game-actions">
                          <button className="btn btn-secondary" type="button" onClick={() => openGameAlerts(game)}>Alert settings</button>
                          <button
                            className="btn btn-secondary games-action-cell"
                            disabled={busyGameId === game.id || unfollowGameMutation.isPending}
                            onClick={async () => {
                              setBusyGameId(game.id);
                              try {
                                await unfollowGameMutation.mutateAsync(game.id);
                              } finally {
                                setBusyGameId(null);
                              }
                            }}
                          >
                            Unfollow
                          </button>
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        </div>
      ) : null}

      {alertGame ? (
        <div className="overlay-sheet" role="dialog" aria-modal="true">
          <section className="overlay-card">
            <header className="overlay-card-header">
              <h4>Game Alert Settings</h4>
              <button className="btn btn-secondary" type="button" onClick={() => { setAlertGame(null); setGameAlertState(null); }}>Close</button>
            </header>
            <p className="muted">{teamMap.get(alertGame.away_team_id)?.abbreviation} @ {teamMap.get(alertGame.home_team_id)?.abbreviation}</p>
            {alertsBusy && !gameAlertState ? <p className="muted">Loading alert settings...</p> : null}
            {gameAlertState ? (
              <ul className="list">
                {gameAlertState.items.map((item) => (
                  <li key={item.alert_type} className="row-card following-alert-rule-row">
                    <div className="following-alert-rule-header">
                      <strong>{PREFERENCE_LABELS[item.alert_type] ?? item.alert_type}</strong>
                      <label className="following-alert-default-toggle">
                        <input
                          type="checkbox"
                          checked={item.use_league_default}
                          disabled={alertsBusy}
                          onChange={(event) => {
                            if (event.target.checked) {
                              clearAlertOverride(gameAlertState.game_id, item.alert_type).catch(() => undefined);
                            } else {
                              applyAlertOverride(gameAlertState.game_id, item.alert_type, {
                                is_enabled_override: item.is_enabled,
                                close_game_margin_threshold_override: item.alert_type === "close_game_late" ? item.close_game_margin_threshold : null,
                                close_game_time_threshold_seconds_override: item.alert_type === "close_game_late" ? item.close_game_time_threshold_seconds : null,
                                inning_start_threshold_override: item.alert_type === "inning_start" ? item.inning_start_threshold : null,
                              }).catch(() => undefined);
                            }
                          }}
                        />
                        Use league default
                      </label>
                    </div>
                    <div className="following-alert-rule-controls">
                      <label>Enabled
                        <select
                          value={item.is_enabled ? "on" : "off"}
                          disabled={alertsBusy || item.use_league_default}
                              onChange={(event) => {
                                applyAlertOverride(gameAlertState.game_id, item.alert_type, {
                                  is_enabled_override: event.target.value === "on",
                                  close_game_margin_threshold_override: item.override?.close_game_margin_threshold_override ?? null,
                                  close_game_time_threshold_seconds_override: item.override?.close_game_time_threshold_seconds_override ?? null,
                                  inning_start_threshold_override: item.override?.inning_start_threshold_override ?? null,
                                }).catch(() => undefined);
                              }}
                        >
                          <option value="on">On</option>
                          <option value="off">Off</option>
                        </select>
                      </label>
                      {item.alert_type === "close_game_late" ? (
                        <>
                          <label>Margin
                            <select
                              value={item.close_game_margin_threshold ?? 5}
                              disabled={alertsBusy || item.use_league_default}
                              onChange={(event) => {
                                applyAlertOverride(gameAlertState.game_id, item.alert_type, {
                                  is_enabled_override: item.override?.is_enabled_override ?? item.is_enabled,
                                  close_game_margin_threshold_override: Number(event.target.value),
                                  close_game_time_threshold_seconds_override: item.close_game_time_threshold_seconds ?? 120,
                                }).catch(() => undefined);
                              }}
                            >
                              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => <option key={value} value={value}>{value}</option>)}
                            </select>
                          </label>
                          <label>Seconds
                            <select
                              value={item.close_game_time_threshold_seconds ?? 120}
                              disabled={alertsBusy || item.use_league_default}
                              onChange={(event) => {
                                applyAlertOverride(gameAlertState.game_id, item.alert_type, {
                                  is_enabled_override: item.override?.is_enabled_override ?? item.is_enabled,
                                  close_game_margin_threshold_override: item.close_game_margin_threshold ?? 5,
                                  close_game_time_threshold_seconds_override: Number(event.target.value),
                                }).catch(() => undefined);
                              }}
                            >
                              {[30, 60, 90, 120, 180, 300].map((value) => <option key={value} value={value}>{value}</option>)}
                            </select>
                          </label>
                        </>
                      ) : null}
                      {item.alert_type === "inning_start" ? (
                        <label>Inning
                          <select
                            value={item.inning_start_threshold ?? 7}
                            disabled={alertsBusy || item.use_league_default}
                            onChange={(event) => {
                              applyAlertOverride(gameAlertState.game_id, item.alert_type, {
                                is_enabled_override: item.override?.is_enabled_override ?? item.is_enabled,
                                inning_start_threshold_override: Number(event.target.value),
                                close_game_margin_threshold_override: null,
                                close_game_time_threshold_seconds_override: null,
                              }).catch(() => undefined);
                            }}
                          >
                            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((value) => <option key={value} value={value}>{value}</option>)}
                          </select>
                        </label>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        </div>
      ) : null}
    </section>
  );
}
