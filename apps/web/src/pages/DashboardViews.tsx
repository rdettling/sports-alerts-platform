import { useEffect, useMemo, useState } from "react";

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

export function GamesView({ token }: { token: string }) {
  const [games, setGames] = useState<Game[]>([]);
  const [teamMap, setTeamMap] = useState<Map<number, Team>>(new Map());
  const [followedGameIds, setFollowedGameIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);

  const load = async () => {
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
  };

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, []);

  const now = Date.now();
  const liveGames = useMemo(
    () => games.filter((game) => game.status === "in_progress" || game.status === "live"),
    [games],
  );
  const startingSoonGames = useMemo(
    () =>
      games.filter((game) => {
        if (game.status !== "scheduled") {
          return false;
        }
        const startsInMs = new Date(game.scheduled_start_time).getTime() - now;
        return startsInMs >= 0 && startsInMs <= 6 * 60 * 60 * 1000;
      }),
    [games, now],
  );

  const sortedGames = useMemo(
    () => [...games].sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()),
    [games],
  );
  const followedGames = useMemo(() => sortedGames.filter((game) => followedGameIds.has(game.id)), [sortedGames, followedGameIds]);

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
      <SectionHeader
        title="Followed Games"
        disabled={loading || busyGameId !== null}
        onRefresh={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}
      />
      {!loading ? (
        <div className="chip-row">
          <span className="chip chip-live">Live now: {liveGames.length}</span>
          <span className="chip chip-neutral">Starting soon (6h): {startingSoonGames.length}</span>
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading games...</p> : null}

      {!loading ? (
        <ul className="list">
          {sortedGames.map((game) => {
            const home = teamMap.get(game.home_team_id);
            const away = teamMap.get(game.away_team_id);
            const isFollowed = followedGameIds.has(game.id);
            if (!home || !away) {
              return null;
            }
            return (
              <li key={game.id} className="game-card">
                <div className="game-card-main">
                  <div className="muted">{formatTipoff(game.scheduled_start_time)}</div>
                  <div className="matchup-row">
                    <TeamLogo team={away} />
                    <span className="matchup-code">{away.abbreviation}</span>
                    <span className="muted">@</span>
                    <TeamLogo team={home} />
                    <span className="matchup-code">{home.abbreviation}</span>
                    {scoreSnippet(game) ? <span className="score-pill">{scoreSnippet(game)}</span> : null}
                    <span className={`chip ${statusClass(game.status)}`}>{GAME_STATUS_LABELS[game.status] ?? game.status}</span>
                  </div>
                </div>
                <button
                  className={isFollowed ? "btn-secondary" : ""}
                  disabled={busyGameId === game.id}
                  onClick={() => onToggleFollow(game.id, isFollowed)}
                >
                  {isFollowed ? "Unfollow" : "Follow"}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
      {!loading && sortedGames.length === 0 ? <p>No upcoming/live games available yet.</p> : null}
      {!loading && followedGames.length === 0 ? <p>No followed games yet.</p> : null}
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
