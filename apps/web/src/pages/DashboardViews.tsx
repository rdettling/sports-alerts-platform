import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  AlertHistoryItem,
  AlertType,
  AlertPreference,
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
  return ` • ${game.away_score}-${game.home_score}`;
}

const GAME_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "Live",
  final: "Final",
  postponed: "Postponed",
};

export function OverviewView() {
  return (
    <section className="card">
      <h2>Overview</h2>
      <p>Use the tabs to follow teams/games and configure your alert preferences.</p>
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

  const onFollow = async (event: FormEvent) => {
    event.preventDefault();
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
      <h2>Followed Teams</h2>
      <button disabled={busy || loading} onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}>
        Refresh
      </button>
      <form className="inline-form" onSubmit={onFollow}>
        <select value={selectedTeamId ?? ""} onChange={(event) => setSelectedTeamId(Number(event.target.value))}>
          {allTeams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name} ({team.abbreviation})
            </option>
          ))}
        </select>
        <button type="submit" disabled={busy || !selectedTeamId}>
          Follow Team
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading teams...</p> : null}
      <ul className="list">
        {followedTeams.map((team) => (
          <li key={team.id}>
            <span>
              {team.name} ({team.abbreviation})
            </span>
            <button disabled={busy} onClick={() => onUnfollow(team.id)}>
              Unfollow
            </button>
          </li>
        ))}
      </ul>
      {followedTeams.length === 0 && !loading ? <p>No followed teams yet.</p> : null}
    </section>
  );
}

function formatGameLabel(game: Game, teamMap: Map<number, Team>) {
  const home = teamMap.get(game.home_team_id);
  const away = teamMap.get(game.away_team_id);
  const matchup =
    home && away ? `${away.abbreviation} @ ${home.abbreviation}` : `Game ${game.external_game_id}`;
  const tipoff = new Date(game.scheduled_start_time).toLocaleString();
  const status = GAME_STATUS_LABELS[game.status] ?? game.status;
  return `${tipoff} • ${matchup}${scoreSnippet(game)} (${status})`;
}

export function GamesView({ token }: { token: string }) {
  const [games, setGames] = useState<Game[]>([]);
  const [teamMap, setTeamMap] = useState<Map<number, Team>>(new Map());
  const [followedGameIds, setFollowedGameIds] = useState<Set<number>>(new Set());
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const [availableGames, follows, teams] = await Promise.all([listGames(), listFollows(token), listTeams()]);
      setGames(availableGames);
      setTeamMap(new Map(teams.map((team) => [team.id, team])));
      setFollowedGameIds(new Set(follows.games.map((game) => game.id)));
      if (!selectedGameId && availableGames.length > 0) {
        setSelectedGameId(availableGames[0].id);
      }
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
  const followedGames = useMemo(() => games.filter((game) => followedGameIds.has(game.id)), [games, followedGameIds]);

  const onFollow = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedGameId) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await followGame(token, selectedGameId);
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  const onUnfollow = async (gameId: number) => {
    setError(null);
    setBusy(true);
    try {
      await unfollowGame(token, gameId);
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h2>Followed Games</h2>
      <button disabled={busy || loading} onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}>
        Refresh
      </button>
      {loading ? <p>Loading games...</p> : null}
      {!loading && liveGames.length > 0 ? (
        <p>
          Live now: {liveGames.length} game{liveGames.length === 1 ? "" : "s"}
        </p>
      ) : null}
      {!loading && startingSoonGames.length > 0 ? (
        <p>
          Starting soon (next 6h): {startingSoonGames.length} game{startingSoonGames.length === 1 ? "" : "s"}
        </p>
      ) : null}
      {games.length > 0 ? (
        <form className="inline-form" onSubmit={onFollow}>
          <select value={selectedGameId ?? ""} onChange={(event) => setSelectedGameId(Number(event.target.value))}>
            {games.map((game) => (
                <option key={game.id} value={game.id}>
                {formatGameLabel(game, teamMap)}
                </option>
              ))}
          </select>
          <button type="submit" disabled={busy || !selectedGameId}>
            Follow Game
          </button>
        </form>
      ) : (
        <p>No upcoming/live games available yet.</p>
      )}
      {error ? <p className="error">{error}</p> : null}
      <ul className="list">
        {followedGames.map((game) => (
          <li key={game.id}>
            <span>{formatGameLabel(game, teamMap)}</span>
            <button disabled={busy} onClick={() => onUnfollow(game.id)}>
              Unfollow
            </button>
          </li>
        ))}
      </ul>
      {followedGames.length === 0 && !loading ? <p>No followed games yet.</p> : null}
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
      <h2>Alert Preferences</h2>
      <button
        disabled={busyAlertType !== null || loading}
        onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}
      >
        Refresh
      </button>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p>Loading preferences...</p> : null}
      <ul className="list">
        {preferences.map((preference) => (
          <li key={preference.alert_type}>
            <span>
              {preference.alert_type} {preference.is_enabled ? "enabled" : "disabled"}
              {preference.alert_type === "close_game_late"
                ? ` • margin=${preference.close_game_margin_threshold ?? "-"} • seconds=${
                    preference.close_game_time_threshold_seconds ?? "-"
                  }`
                : ""}
            </span>
            <button disabled={busyAlertType === preference.alert_type} onClick={() => onToggle(preference)}>
              {preference.is_enabled ? "Disable" : "Enable"}
            </button>
          </li>
        ))}
      </ul>
      <button disabled={busyAlertType === "close_game_late"} onClick={onCloseGameDefaults}>
        Reset close_game_late to defaults
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
      <h2>Alert History</h2>
      <button onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))} disabled={loading}>
        Refresh
      </button>
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
          <li key={item.id}>
            <span>
              {new Date(item.sent_at).toLocaleString()} • {item.away_team_abbreviation} @ {item.home_team_abbreviation} •{" "}
              {item.alert_type} • {item.delivery_status}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
