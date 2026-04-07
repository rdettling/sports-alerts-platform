import { useCallback, useEffect, useMemo, useState } from "react";

import { Game, Team, followGame, listFollows, listGames, listTeams, unfollowGame } from "../../api";
import {
  TeamLogo,
  compactStatusText,
  formatMoneyline,
  formatTipoff,
  messageFromUnknown,
  noVigProbabilities,
} from "./shared";

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
