import { useCallback, useEffect, useMemo, useState } from "react";

import { Team, followGame, listAlertHistory, listFollows, listGames, listTeams, unfollowGame } from "../../api";
import { useDashboardShell } from "./shell";
import {
  TeamLogo,
  compactStatusText,
  formatGameTime,
  formatMoneyline,
  messageFromUnknown,
  noVigProbabilities,
} from "./shared";

export function GamesView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();
  const [games, setGames] = useState<Awaited<ReturnType<typeof listGames>>>([]);
  const [teamMap, setTeamMap] = useState<Map<number, Team>>(new Map());
  const [followedGameIds, setFollowedGameIds] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState<"all" | "live" | "today" | "following">("all");
  const [teamFilter, setTeamFilter] = useState<number | "all">("all");
  const [query, setQuery] = useState("");
  const [sentAlerts24h, setSentAlerts24h] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [availableGames, follows, teams, alerts24h] = await Promise.all([
        listGames(),
        listFollows(token),
        listTeams(),
        listAlertHistory(token, { sinceHours: 24, limit: 200 }),
      ]);
      setGames(availableGames);
      setTeamMap(new Map(teams.map((team) => [team.id, team])));
      setFollowedGameIds(new Set(follows.games.map((game) => game.id)));
      setSentAlerts24h(alerts24h.items.filter((item) => item.delivery_status === "sent").length);
      setLastSync(new Date());
    } finally {
      setLoading(false);
    }
  }, [setLastSync, token]);

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

  const availableTeams = useMemo(() => {
    const ids = new Set<number>();
    sortedGames.forEach((game) => {
      ids.add(game.away_team_id);
      ids.add(game.home_team_id);
    });
    return Array.from(ids)
      .map((id) => teamMap.get(id))
      .filter((team): team is Team => Boolean(team))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [sortedGames, teamMap]);

  const activeFollowedGameCount = useMemo(
    () => sortedGames.filter((game) => followedGameIds.has(game.id)).length,
    [sortedGames, followedGameIds],
  );

  const visibleGames = useMemo(() => {
    let result = sortedGames;

    if (filter === "live") {
      result = result.filter((game) => game.status === "in_progress" || game.status === "live");
    } else if (filter === "today") {
      result = result.filter((game) => todayGameIds.has(game.id));
    } else if (filter === "following") {
      result = result.filter((game) => followedGameIds.has(game.id));
    }

    if (teamFilter !== "all") {
      result = result.filter((game) => game.home_team_id === teamFilter || game.away_team_id === teamFilter);
    }

    const q = query.trim().toLowerCase();
    if (q) {
      result = result.filter((game) => {
        const home = teamMap.get(game.home_team_id);
        const away = teamMap.get(game.away_team_id);
        const hay = `${home?.name ?? ""} ${home?.abbreviation ?? ""} ${away?.name ?? ""} ${away?.abbreviation ?? ""}`.toLowerCase();
        return hay.includes(q);
      });
    }

    return result;
  }, [filter, followedGameIds, query, sortedGames, teamFilter, teamMap, todayGameIds]);

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
    <section className="view-stack">
      <div className="metric-grid">
        <article className="metric-card">
          <span>Live</span>
          <strong>{liveGames.length}</strong>
        </article>
        <article className="metric-card">
          <span>Today</span>
          <strong>{todayGames.length}</strong>
        </article>
        <article className="metric-card">
          <span>Following</span>
          <strong>{activeFollowedGameCount}</strong>
        </article>
        <article className="metric-card">
          <span>Alerts Sent 24h</span>
          <strong>{sentAlerts24h}</strong>
        </article>
      </div>

      <section className="panel">
        <div className="section-header">
          <h3>Game Board</h3>
          <p>Track tipoff times, probabilities, and follow actions in one place.</p>
        </div>

        <div className="toolbar unified-toolbar">
          <input
            placeholder="Search team or abbreviation"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="search-input"
          />
          <select value={teamFilter} onChange={(event) => setTeamFilter(event.target.value === "all" ? "all" : Number(event.target.value))}>
            <option value="all">All teams</option>
            {availableTeams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name} ({team.abbreviation})
              </option>
            ))}
          </select>
          <div className="chip-row">
            <button className={`chip-btn ${filter === "all" ? "active" : ""}`.trim()} onClick={() => setFilter("all")} disabled={loading}>All</button>
            <button className={`chip-btn ${filter === "live" ? "active" : ""}`.trim()} onClick={() => setFilter("live")} disabled={loading}>Live ({liveGames.length})</button>
            <button className={`chip-btn ${filter === "today" ? "active" : ""}`.trim()} onClick={() => setFilter("today")} disabled={loading}>Today ({todayGames.length})</button>
            <button className={`chip-btn ${filter === "following" ? "active" : ""}`.trim()} onClick={() => setFilter("following")} disabled={loading}>Following ({activeFollowedGameCount})</button>
          </div>
          <button className="btn btn-secondary" disabled={loading || busyGameId !== null} onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}>Refresh</button>
        </div>

        {error ? <p className="error">{error}</p> : null}
        {loading ? <p className="muted">Loading games...</p> : null}

        {!loading ? (
          <div className="data-table-wrap">
            <div className="data-table-head games-table-grid">
              <span>Time</span>
              <span>Matchup</span>
              <span>Win %</span>
              <span>Edge</span>
              <span>Odds</span>
              <span>Book</span>
              <span>Action</span>
            </div>
            <ul className="list data-table-list">
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
                  <li key={game.id} className="data-table-row games-table-grid">
                    <div className="games-time-cell">
                      <span>{formatGameTime(game)}</span>
                      {statusText ? <span className="muted games-row-subtext">{statusText}</span> : null}
                    </div>
                    <div className="team-row">
                      <TeamLogo team={away} size={18} />
                      <strong>{away.abbreviation}</strong>
                      <span className="muted">@</span>
                      <TeamLogo team={home} size={18} />
                      <strong>{home.abbreviation}</strong>
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
                      className={`btn ${isFollowed ? "btn-secondary" : ""} games-action-cell`.trim()}
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
        {!loading && visibleGames.length === 0 ? <p className="muted">No games in this filter.</p> : null}
      </section>
    </section>
  );
}
