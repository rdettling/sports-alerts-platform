import { useCallback, useEffect, useMemo, useState } from "react";

import {
  AlertHistoryItem,
  AlertPreference,
  AlertType,
  Game,
  Team,
  followGame,
  followTeam,
  listAlertHistory,
  listAlertPreferences,
  listFollows,
  listGames,
  listTeams,
  unfollowGame,
  unfollowTeam,
  updateAlertPreference,
} from "../api";

function messageFromUnknown(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

function scoreSnippet(game: Game): string {
  if (game.home_score === null || game.away_score === null) {
    return "";
  }
  return `${game.away_score}-${game.home_score}`;
}

function teamLogoUrl(team: Team): string {
  return `https://cdn.nba.com/logos/nba/${team.external_team_id}/global/L/logo.svg`;
}

function TeamLogo({ team, size = 26 }: { team: Team; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="team-logo-fallback" style={{ width: size, height: size }}>
        {team.abbreviation.slice(0, 2)}
      </span>
    );
  }
  return (
    <img
      className="team-logo"
      src={teamLogoUrl(team)}
      width={size}
      height={size}
      alt={`${team.name} logo`}
      onError={() => setFailed(true)}
    />
  );
}

const GAME_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "Live",
  final: "Final",
  postponed: "Postponed",
};

const PREFERENCE_LABELS: Record<string, string> = {
  game_start: "Game start",
  close_game_late: "Close game late",
  final_result: "Final result",
};

const ALERT_TYPE_LABELS: Record<string, string> = {
  game_start: "Game start",
  close_game_late: "Close game late",
  final_result: "Final result",
};

function statusClass(status: string): string {
  if (status === "in_progress" || status === "live") return "chip-live";
  if (status === "final") return "chip-final";
  return "chip-neutral";
}

function deliveryStatusClass(status: string): string {
  if (status === "sent") return "chip-final";
  if (status === "failed") return "chip-error";
  return "chip-neutral";
}

function SectionHeader({
  title,
  onRefresh,
  disabled,
}: {
  title: string;
  onRefresh: () => void;
  disabled: boolean;
}) {
  return (
    <div className="section-header">
      <h2>{title}</h2>
      <button className="btn-secondary" disabled={disabled} onClick={onRefresh}>
        Refresh
      </button>
    </div>
  );
}

export function OverviewView() {
  return (
    <section className="card">
      <h2>Overview</h2>
      <p>Use tabs to follow teams and games, manage preferences, and view alert history.</p>
    </section>
  );
}

export function TeamsView({ token }: { token: string }) {
  const [allTeams, setAllTeams] = useState<Team[]>([]);
  const [followedTeamIds, setFollowedTeamIds] = useState<Set<number>>(new Set());
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const [teams, follows] = await Promise.all([listTeams(), listFollows(token)]);
      setAllTeams(teams);
      setFollowedTeamIds(new Set(follows.teams.map((team) => team.id)));
      if (!selectedTeamId && teams.length > 0) {
        setSelectedTeamId(teams[0].id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, []);

  const followedTeams = useMemo(
    () => allTeams.filter((team) => followedTeamIds.has(team.id)),
    [allTeams, followedTeamIds],
  );

  const onFollow = async () => {
    if (!selectedTeamId) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await followTeam(token, selectedTeamId);
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  const onUnfollow = async (teamId: number) => {
    setError(null);
    setBusy(true);
    try {
      await unfollowTeam(token, teamId);
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <SectionHeader
        title="Followed Teams"
        disabled={busy || loading}
        onRefresh={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}
      />
      <div className="inline-form">
        <select value={selectedTeamId ?? ""} onChange={(event) => setSelectedTeamId(Number(event.target.value))}>
          {allTeams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name} ({team.abbreviation})
            </option>
          ))}
        </select>
        <button type="button" disabled={busy || !selectedTeamId} onClick={onFollow}>
          Follow Team
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading teams...</p> : null}
      <ul className="list">
        {followedTeams.map((team) => (
          <li key={team.id} className="row-card">
            <span className="team-row">
              <TeamLogo team={team} />
              <span>
                {team.name} <span className="muted">({team.abbreviation})</span>
              </span>
            </span>
            <button className="btn-secondary" disabled={busy} onClick={() => onUnfollow(team.id)}>
              Unfollow
            </button>
          </li>
        ))}
      </ul>
      {followedTeams.length === 0 && !loading ? <p>No followed teams yet.</p> : null}
    </section>
  );
}

function formatTipoff(dateIso: string): string {
  return new Date(dateIso).toLocaleString([], { month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function formatMoneyline(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return value > 0 ? `+${value}` : `${value}`;
}

function impliedProbabilityFromAmericanOdds(odds: number | null): number | null {
  if (odds === null || odds === 0) {
    return null;
  }
  if (odds > 0) {
    return 100 / (odds + 100);
  }
  const absoluteOdds = Math.abs(odds);
  return absoluteOdds / (absoluteOdds + 100);
}

function noVigProbabilities(game: Game): { home: number; away: number } | null {
  if (!game.odds) {
    return null;
  }
  const rawHome = impliedProbabilityFromAmericanOdds(game.odds.home_moneyline);
  const rawAway = impliedProbabilityFromAmericanOdds(game.odds.away_moneyline);
  if (rawHome === null || rawAway === null) {
    return null;
  }
  const total = rawHome + rawAway;
  if (total <= 0) {
    return null;
  }
  return {
    home: rawHome / total,
    away: rawAway / total,
  };
}

function compactStatusText(game: Game): string | null {
  if (game.status === "scheduled") {
    return null;
  }
  const parts = [GAME_STATUS_LABELS[game.status] ?? game.status];
  const score = scoreSnippet(game);
  if (score) {
    parts.push(score);
  }
  return parts.join(" • ");
}

function isGameActive(game: Game): boolean {
  return !game.is_final && game.status !== "final";
}

function isRecentlyCompletedGame(game: Game, nowMs: number): boolean {
  if (isGameActive(game)) {
    return false;
  }
  const startedAtMs = new Date(game.scheduled_start_time).getTime();
  return nowMs - startedAtMs <= 24 * 60 * 60 * 1000;
}

export function GamesView({ token }: { token: string }) {
  const [games, setGames] = useState<Game[]>([]);
  const [teamMap, setTeamMap] = useState<Map<number, Team>>(new Map());
  const [followedGameIds, setFollowedGameIds] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState<"all" | "live" | "today" | "following">("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [availableGames, follows, teams] = await Promise.all([listGames(), listFollows(token), listTeams()]);
      setGames(availableGames);
      setTeamMap(new Map(teams.map((team) => [team.id, team])));
      setFollowedGameIds(new Set(follows.games.map((game) => game.id)));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, [load]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
    }, 120_000);
    return () => window.clearInterval(intervalId);
  }, [load]);

  const liveGames = useMemo(
    () => games.filter((game) => game.status === "in_progress" || game.status === "live"),
    [games],
  );
  const todayGames = useMemo(
    () =>
      games.filter((game) => {
        const today = new Date();
        const y = today.getFullYear();
        const m = today.getMonth();
        const d = today.getDate();
        const gameDate = new Date(game.scheduled_start_time);
        return gameDate.getFullYear() === y && gameDate.getMonth() === m && gameDate.getDate() === d;
      }),
    [games],
  );
  const todayGameIds = useMemo(() => new Set(todayGames.map((game) => game.id)), [todayGames]);

  const sortedGames = useMemo(
    () => [...games].sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()),
    [games],
  );
  const activeFollowedGameCount = useMemo(
    () => sortedGames.filter((game) => followedGameIds.has(game.id)).length,
    [sortedGames, followedGameIds],
  );
  const visibleGames = useMemo(() => {
    if (filter === "all") return sortedGames;
    if (filter === "live") {
      return sortedGames.filter((game) => game.status === "in_progress" || game.status === "live");
    }
    if (filter === "today") {
      return sortedGames.filter((game) => todayGameIds.has(game.id));
    }
    return sortedGames.filter((game) => followedGameIds.has(game.id));
  }, [filter, sortedGames, followedGameIds, todayGameIds]);

  const onToggleFollow = async (gameId: number, isFollowed: boolean) => {
    setError(null);
    setBusyGameId(gameId);
    try {
      if (isFollowed) {
        await unfollowGame(token, gameId);
      } else {
        await followGame(token, gameId);
      }
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyGameId(null);
    }
  };

  return (
    <section className="card">
      <div className="games-header">
        <h2>Games</h2>
        <div className="games-toolbar">
          <div className="games-filter-row">
            <button className={filter === "all" ? "" : "btn-secondary"} onClick={() => setFilter("all")} disabled={loading}>
              All
            </button>
            <button className={filter === "live" ? "" : "btn-secondary"} onClick={() => setFilter("live")} disabled={loading}>
              Live ({liveGames.length})
            </button>
            <button className={filter === "today" ? "" : "btn-secondary"} onClick={() => setFilter("today")} disabled={loading}>
              Today ({todayGames.length})
            </button>
            <button
              className={filter === "following" ? "" : "btn-secondary"}
              onClick={() => setFilter("following")}
              disabled={loading}
            >
              Following ({activeFollowedGameCount})
            </button>
          </div>
          <button
            className="btn-secondary"
            disabled={loading || busyGameId !== null}
            onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}
          >
            Refresh
          </button>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading games...</p> : null}

      {!loading ? (
        <div className="games-table-wrap">
          <div className="games-table-head">
            <span>Time</span>
            <span>Matchup</span>
            <span>Win %</span>
            <span>Edge</span>
            <span>Odds</span>
            <span>Book</span>
            <span>Action</span>
          </div>
          <ul className="list games-table-list">
            {visibleGames.map((game) => {
              const home = teamMap.get(game.home_team_id);
              const away = teamMap.get(game.away_team_id);
              const isFollowed = followedGameIds.has(game.id);
              const probabilities = noVigProbabilities(game);
              const awayPercent = probabilities ? Math.round(probabilities.away * 100) : null;
              const homePercent = awayPercent !== null ? 100 - awayPercent : null;
              const statusText = compactStatusText(game);
              if (!home || !away) {
                return null;
              }
              return (
                <li key={game.id} className="games-table-row">
                  <div className="games-time-cell">
                    <span>{formatTipoff(game.scheduled_start_time)}</span>
                    {statusText ? <span className="muted games-row-subtext">{statusText}</span> : null}
                  </div>
                  <div className="matchup-row">
                    <TeamLogo team={away} size={18} />
                    <span className="matchup-code">{away.abbreviation}</span>
                    <span className="muted">@</span>
                    <TeamLogo team={home} size={18} />
                    <span className="matchup-code">{home.abbreviation}</span>
                  </div>
                  <div className="games-win-cell">{probabilities ? `${awayPercent}% / ${homePercent}%` : "—"}</div>
                  <div className="games-bar-cell">
                    {probabilities ? (
                      <div className="probability-bar" aria-label="Win probability">
                        <div className="probability-away" style={{ width: `${probabilities.away * 100}%` }} />
                        <div className="probability-home" style={{ width: `${probabilities.home * 100}%` }} />
                      </div>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </div>
                  <div className="games-odds-cell">
                    {game.odds ? `${formatMoneyline(game.odds.away_moneyline)} / ${formatMoneyline(game.odds.home_moneyline)}` : "—"}
                  </div>
                  <div className="muted games-book-cell">{game.odds?.bookmaker ?? "—"}</div>
                  <button
                    className={`${isFollowed ? "btn-secondary" : ""} game-action-button games-action-cell`.trim()}
                    disabled={busyGameId === game.id}
                    onClick={() => onToggleFollow(game.id, isFollowed)}
                  >
                    {isFollowed ? "Unfollow" : "Follow"}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {!loading && visibleGames.length === 0 ? <p>No games in this filter.</p> : null}
    </section>
  );
}

export function FollowingView({ token }: { token: string }) {
  const [allTeams, setAllTeams] = useState<Team[]>([]);
  const [followedTeamIds, setFollowedTeamIds] = useState<Set<number>>(new Set());
  const [games, setGames] = useState<Game[]>([]);
  const [teamMap, setTeamMap] = useState<Map<number, Team>>(new Map());
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [gamesTab, setGamesTab] = useState<"active" | "recent">("active");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [addingTeam, setAddingTeam] = useState(false);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const [follows, teams] = await Promise.all([listFollows(token), listTeams()]);
      setAllTeams(teams);
      setFollowedTeamIds(new Set(follows.teams.map((team) => team.id)));
      setGames(follows.games.sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()));
      setTeamMap(new Map(teams.map((team) => [team.id, team])));
      if (!selectedTeamId && teams.length > 0) {
        setSelectedTeamId(teams[0].id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, []);

  const onUnfollowGame = async (gameId: number) => {
    setError(null);
    setBusyGameId(gameId);
    try {
      await unfollowGame(token, gameId);
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyGameId(null);
    }
  };

  const onFollowTeam = async () => {
    if (!selectedTeamId) {
      return;
    }
    setError(null);
    setAddingTeam(true);
    try {
      await followTeam(token, selectedTeamId);
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setAddingTeam(false);
    }
  };

  const onUnfollowTeam = async (teamId: number) => {
    setError(null);
    setBusyTeamId(teamId);
    try {
      await unfollowTeam(token, teamId);
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyTeamId(null);
    }
  };

  const nowMs = Date.now();
  const followedTeams = useMemo(
    () => allTeams.filter((team) => followedTeamIds.has(team.id)),
    [allTeams, followedTeamIds],
  );
  const activeGames = useMemo(
    () =>
      games
        .filter((game) => isGameActive(game))
        .sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()),
    [games],
  );
  const recentCompletedGames = useMemo(
    () =>
      games
        .filter((game) => isRecentlyCompletedGame(game, nowMs))
        .sort((a, b) => new Date(b.scheduled_start_time).getTime() - new Date(a.scheduled_start_time).getTime()),
    [games, nowMs],
  );
  const shownGames = gamesTab === "active" ? activeGames : recentCompletedGames;

  return (
    <section className="card">
      <div className="following-header">
        <h2>Following</h2>
        <button className="btn-secondary" disabled={loading || busyGameId !== null || addingTeam} onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}>
          Refresh
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading following data...</p> : null}
      {!loading ? (
        <div className="following-grid">
          <div className="following-panel">
            <h3>Teams</h3>
            <div className="inline-form">
              <select value={selectedTeamId ?? ""} onChange={(event) => setSelectedTeamId(Number(event.target.value))}>
                {allTeams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name} ({team.abbreviation})
                  </option>
                ))}
              </select>
              <button type="button" disabled={addingTeam || !selectedTeamId} onClick={onFollowTeam}>
                Follow Team
              </button>
            </div>
            {followedTeams.length === 0 ? <p className="muted">No followed teams yet.</p> : null}
            <ul className="list">
              {followedTeams.map((team) => (
                <li key={team.id} className="row-card">
                  <span className="team-row">
                    <TeamLogo team={team} size={22} />
                    <span>
                      {team.name} <span className="muted">({team.abbreviation})</span>
                    </span>
                  </span>
                  <button className="btn-secondary" disabled={busyTeamId === team.id} onClick={() => onUnfollowTeam(team.id)}>
                    Unfollow
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="following-panel">
            <h3>Games</h3>
            <div className="following-games-tabs">
              <button className={gamesTab === "active" ? "" : "btn-secondary"} onClick={() => setGamesTab("active")}>
                Active ({activeGames.length})
              </button>
              <button className={gamesTab === "recent" ? "" : "btn-secondary"} onClick={() => setGamesTab("recent")}>
                Recent 24h ({recentCompletedGames.length})
              </button>
            </div>
            {shownGames.length === 0 ? (
              <p className="muted">{gamesTab === "active" ? "No active followed games." : "No recently completed followed games."}</p>
            ) : null}
          <ul className="list">
              {shownGames.map((game) => {
              const away = teamMap.get(game.away_team_id);
              const home = teamMap.get(game.home_team_id);
              if (!away || !home) {
                return null;
              }
              return (
                <li key={game.id} className="row-card">
                  <span className="team-row">
                    <TeamLogo team={away} size={20} />
                    <strong>{away.abbreviation}</strong>
                    <span className="muted">@</span>
                    <TeamLogo team={home} size={20} />
                    <strong>{home.abbreviation}</strong>
                    <span className="muted">
                      {!isGameActive(game)
                        ? ` • ${scoreSnippet(game) || formatTipoff(game.scheduled_start_time)} • Final`
                        : ` • ${formatTipoff(game.scheduled_start_time)}`}
                    </span>
                  </span>
                  <button className="btn-secondary" disabled={busyGameId === game.id} onClick={() => onUnfollowGame(game.id)}>
                    Unfollow
                  </button>
                </li>
              );
            })}
          </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function PreferencesView({ token }: { token: string }) {
  const [preferences, setPreferences] = useState<AlertPreference[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAlertType, setBusyAlertType] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await listAlertPreferences(token);
      setPreferences(response);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, []);

  const onToggle = async (preference: AlertPreference) => {
    setError(null);
    setBusyAlertType(preference.alert_type);
    try {
      await updateAlertPreference(token, preference.alert_type, { is_enabled: !preference.is_enabled });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const onCloseGameDefaults = async () => {
    setError(null);
    setBusyAlertType("close_game_late");
    try {
      await updateAlertPreference(token, "close_game_late", {
        is_enabled: true,
        close_game_margin_threshold: 5,
        close_game_time_threshold_seconds: 120,
      });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  return (
    <section className="card">
      <SectionHeader
        title="Alert Preferences"
        disabled={busyAlertType !== null || loading}
        onRefresh={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}
      />
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading preferences...</p> : null}
      <ul className="list">
        {preferences.map((preference) => (
          <li key={preference.alert_type} className="row-card">
            <span>
              <strong>{PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type}</strong>{" "}
              <span className={`chip ${preference.is_enabled ? "chip-final" : "chip-neutral"}`}>
                {preference.is_enabled ? "Enabled" : "Disabled"}
              </span>
              {preference.alert_type === "close_game_late"
                ? ` • margin=${preference.close_game_margin_threshold ?? "-"} • seconds=${
                    preference.close_game_time_threshold_seconds ?? "-"
                  }`
                : ""}
            </span>
            <button className="btn-secondary" disabled={busyAlertType === preference.alert_type} onClick={() => onToggle(preference)}>
              {preference.is_enabled ? "Disable" : "Enable"}
            </button>
          </li>
        ))}
      </ul>
      <button className="btn-secondary" disabled={busyAlertType === "close_game_late"} onClick={onCloseGameDefaults}>
        Reset close_game_late defaults
      </button>
    </section>
  );
}

export function HistoryView({ token }: { token: string }) {
  const [items, setItems] = useState<AlertHistoryItem[]>([]);
  const [alertTypeFilter, setAlertTypeFilter] = useState<"all" | AlertType>("all");
  const [timeFilter, setTimeFilter] = useState<"all" | "24h" | "7d">("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await listAlertHistory(token, {
        alertType: alertTypeFilter === "all" ? undefined : alertTypeFilter,
        sinceHours: timeFilter === "24h" ? 24 : timeFilter === "7d" ? 24 * 7 : undefined,
      });
      setItems(response.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, [alertTypeFilter, timeFilter]);

  return (
    <section className="card">
      <SectionHeader
        title="Alert History"
        disabled={loading}
        onRefresh={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}
      />
      <div className="inline-form">
        <select value={alertTypeFilter} onChange={(event) => setAlertTypeFilter(event.target.value as "all" | AlertType)}>
          <option value="all">All alert types</option>
          <option value="game_start">Game start</option>
          <option value="close_game_late">Close game late</option>
          <option value="final_result">Final result</option>
        </select>
        <select value={timeFilter} onChange={(event) => setTimeFilter(event.target.value as "all" | "24h" | "7d")}>
          <option value="all">All time</option>
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
        </select>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading alert history...</p> : null}
      {items.length === 0 && !loading ? <p>No alerts have been sent yet.</p> : null}
      <ul className="list">
        {items.map((item) => (
          <li key={item.id} className="row-card">
            <span>
              {new Date(item.sent_at).toLocaleString()} • {item.away_team_abbreviation} @ {item.home_team_abbreviation} •{" "}
              {ALERT_TYPE_LABELS[item.alert_type] ?? item.alert_type}
            </span>
            <span className={`chip ${deliveryStatusClass(item.delivery_status)}`}>{item.delivery_status}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function AlertsView({ token }: { token: string }) {
  const [preferences, setPreferences] = useState<AlertPreference[]>([]);
  const [items, setItems] = useState<AlertHistoryItem[]>([]);
  const [last24hItems, setLast24hItems] = useState<AlertHistoryItem[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [alertTypeFilter, setAlertTypeFilter] = useState<"all" | AlertType>("all");
  const [timeFilter, setTimeFilter] = useState<"24h" | "7d" | "all">("24h");
  const [statusFilter, setStatusFilter] = useState<"all" | "sent" | "failed" | "pending">("all");
  const [closeGameMarginInput, setCloseGameMarginInput] = useState(5);
  const [closeGameMinutesInput, setCloseGameMinutesInput] = useState(2);
  const [busyAlertType, setBusyAlertType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [preferenceResponse, historyResponse, history24Response, teamsResponse] = await Promise.all([
        listAlertPreferences(token),
        listAlertHistory(token, {
          alertType: alertTypeFilter === "all" ? undefined : alertTypeFilter,
          sinceHours: timeFilter === "24h" ? 24 : timeFilter === "7d" ? 24 * 7 : undefined,
          limit: 200,
        }),
        listAlertHistory(token, { sinceHours: 24, limit: 200 }),
        listTeams(),
      ]);
      setPreferences(preferenceResponse);
      const closePref = preferenceResponse.find((preference) => preference.alert_type === "close_game_late");
      if (closePref) {
        setCloseGameMarginInput(closePref.close_game_margin_threshold ?? 5);
        setCloseGameMinutesInput(Math.max(1, Math.round((closePref.close_game_time_threshold_seconds ?? 120) / 60)));
      }
      setItems(historyResponse.items);
      setLast24hItems(history24Response.items);
      setTeams(teamsResponse);
      setUpdatedAt(new Date());
    } finally {
      setLoading(false);
    }
  }, [alertTypeFilter, timeFilter, token]);

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, [load]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
    }, 120_000);
    return () => window.clearInterval(intervalId);
  }, [load]);

  const onToggle = async (preference: AlertPreference) => {
    setError(null);
    setBusyAlertType(preference.alert_type);
    try {
      await updateAlertPreference(token, preference.alert_type, { is_enabled: !preference.is_enabled });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const onCloseGameSettingChange = async (nextMargin: number, nextMinutes: number) => {
    const closePref = preferences.find((preference) => preference.alert_type === "close_game_late");
    if (!closePref) return;
    setError(null);
    setBusyAlertType("close_game_late");
    try {
      await updateAlertPreference(token, "close_game_late", {
        is_enabled: closePref.is_enabled,
        close_game_margin_threshold: nextMargin,
        close_game_time_threshold_seconds: nextMinutes * 60,
      });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const filteredItems = useMemo(() => {
    if (statusFilter === "all") {
      return items;
    }
    return items.filter((item) => item.delivery_status === statusFilter);
  }, [items, statusFilter]);

  const sent24hCount = useMemo(
    () => last24hItems.filter((item) => item.delivery_status === "sent").length,
    [last24hItems],
  );
  const failed24hCount = useMemo(
    () => last24hItems.filter((item) => item.delivery_status === "failed").length,
    [last24hItems],
  );
  const lastSentAt = useMemo(() => {
    const sentItem = last24hItems.find((item) => item.delivery_status === "sent");
    return sentItem ? new Date(sentItem.sent_at).toLocaleString() : "No sent alerts in last 24h";
  }, [last24hItems]);
  const teamsByAbbreviation = useMemo(
    () => new Map(teams.map((team) => [team.abbreviation.toUpperCase(), team])),
    [teams],
  );

  return (
    <section className="card">
      <div className="alerts-header">
        <h2>Alerts</h2>
        <span className="muted">{updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : "Loading..."}</span>
      </div>
      {error ? <p className="error">{error}</p> : null}

      <div className="alerts-health-grid">
        <div className="alerts-health-card">
          <span className="muted">Last sent</span>
          <strong>{lastSentAt}</strong>
        </div>
        <div className="alerts-health-card">
          <span className="muted">Sent (24h)</span>
          <strong>{sent24hCount}</strong>
        </div>
        <div className="alerts-health-card">
          <span className="muted">Failed (24h)</span>
          <strong>{failed24hCount}</strong>
        </div>
      </div>

      {loading ? <p>Loading alert settings and history...</p> : null}

      {!loading ? (
        <div className="alerts-grid">
          <div className="alerts-panel">
            <h3>Alert Rules</h3>
            <ul className="list">
              {preferences.map((preference) => (
                <li
                  key={preference.alert_type}
                  className={`row-card alert-rule-row ${preference.is_enabled ? "" : "alert-rule-disabled"}`.trim()}
                >
                  <div className="alert-rule-content">
                    <div className="alert-rule-header">
                      <div className="alert-rule-title-wrap">
                        <strong>{PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type}</strong>
                      </div>
                      <button
                        className={`alert-toggle ${preference.is_enabled ? "on" : "off"}`}
                        type="button"
                        role="switch"
                        aria-checked={preference.is_enabled}
                        aria-label={`Toggle ${PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type}`}
                        disabled={busyAlertType === preference.alert_type}
                        onClick={() => onToggle(preference)}
                      >
                        <span className="alert-toggle-track">
                          <span className="alert-toggle-thumb" />
                        </span>
                      </button>
                    </div>
                    {preference.alert_type === "close_game_late" && preference.is_enabled ? (
                      <div className="alert-rule-controls">
                        <label>
                          Margin
                          <select
                            className="alert-rule-select"
                            value={closeGameMarginInput}
                            onChange={(event) => {
                              const nextMargin = Number(event.target.value);
                              setCloseGameMarginInput(nextMargin);
                              onCloseGameSettingChange(nextMargin, closeGameMinutesInput).catch((requestError) =>
                                setError(messageFromUnknown(requestError)),
                              );
                            }}
                            disabled={busyAlertType === "close_game_late"}
                          >
                            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Minutes
                          <select
                            className="alert-rule-select"
                            value={closeGameMinutesInput}
                            onChange={(event) => {
                              const nextMinutes = Number(event.target.value);
                              setCloseGameMinutesInput(nextMinutes);
                              onCloseGameSettingChange(closeGameMarginInput, nextMinutes).catch((requestError) =>
                                setError(messageFromUnknown(requestError)),
                              );
                            }}
                            disabled={busyAlertType === "close_game_late"}
                          >
                            {[1, 2, 3, 4, 5, 10].map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    ) : null}
                    {preference.alert_type === "close_game_late" && !preference.is_enabled ? (
                      <span className="muted alert-rule-subtext">Enable this rule to configure margin and minute thresholds.</span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="alerts-panel">
            <h3>Recent Alerts</h3>
            <div className="alerts-filters">
              <select value={alertTypeFilter} onChange={(event) => setAlertTypeFilter(event.target.value as "all" | AlertType)}>
                <option value="all">All alert types</option>
                <option value="game_start">Game start</option>
                <option value="close_game_late">Close game late</option>
                <option value="final_result">Final result</option>
              </select>
              <select value={timeFilter} onChange={(event) => setTimeFilter(event.target.value as "24h" | "7d" | "all")}>
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
                <option value="all">All time</option>
              </select>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | "sent" | "failed" | "pending")}>
                <option value="all">All statuses</option>
                <option value="sent">Sent</option>
                <option value="failed">Failed</option>
                <option value="pending">Pending</option>
              </select>
            </div>
            {filteredItems.length === 0 ? <p className="muted">No alerts in this filter.</p> : null}
            <ul className="list">
              {filteredItems.map((item) => (
                <li key={item.id} className="row-card">
                  <span className="alert-history-row-main">
                    <span>{new Date(item.sent_at).toLocaleString()}</span>
                    <span className="team-row">
                      {teamsByAbbreviation.get(item.away_team_abbreviation) ? (
                        <TeamLogo team={teamsByAbbreviation.get(item.away_team_abbreviation)!} size={18} />
                      ) : (
                        <span className="team-logo-fallback" style={{ width: 18, height: 18 }}>
                          {item.away_team_abbreviation.slice(0, 2)}
                        </span>
                      )}
                      <strong>{item.away_team_abbreviation}</strong>
                      <span className="muted">@</span>
                      {teamsByAbbreviation.get(item.home_team_abbreviation) ? (
                        <TeamLogo team={teamsByAbbreviation.get(item.home_team_abbreviation)!} size={18} />
                      ) : (
                        <span className="team-logo-fallback" style={{ width: 18, height: 18 }}>
                          {item.home_team_abbreviation.slice(0, 2)}
                        </span>
                      )}
                      <strong>{item.home_team_abbreviation}</strong>
                    </span>
                    <span>{ALERT_TYPE_LABELS[item.alert_type] ?? item.alert_type}</span>
                  </span>
                  <span className={`chip ${deliveryStatusClass(item.delivery_status)}`}>{item.delivery_status}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}
