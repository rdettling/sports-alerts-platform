import { Fragment, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followGame, type Game, type Team, unfollowGame } from "../../../shared/api";
import { TeamLogo, formatGameTime, formatMoneyline, messageFromUnknown, noVigProbabilities } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";
import { useGamesData } from "../hooks/useGamesData";

type GameDayGroup = { label: string; items: Game[] };

export function GamesView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();
  const queryClient = useQueryClient();
  const { data, isLoading, refetch } = useGamesData(token);

  const [filter, setFilter] = useState<"all" | "live" | "today" | "following">("all");
  const [teamFilter, setTeamFilter] = useState<number | "all">("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const toggleMutation = useMutation({
    mutationFn: async ({ gameId, isFollowed }: { gameId: number; isFollowed: boolean }) => {
      if (isFollowed) {
        await unfollowGame(token, gameId);
      } else {
        await followGame(token, gameId);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["games-page", token] });
      setLastSync(new Date());
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const games = data?.games ?? [];
  const follows = data?.follows;
  const teams = data?.teams ?? [];
  const sentAlerts24h = data?.sentAlerts24h ?? 0;

  const teamMap = useMemo(() => new Map(teams.map((team: Team) => [team.id, team])), [teams]);
  const followedTeams = follows?.teams ?? [];
  const followedGameIds = useMemo(() => new Set((follows?.games ?? []).map((game) => game.id)), [follows?.games]);

  const liveGames = useMemo(() => games.filter((game) => game.status === "in_progress" || game.status === "live"), [games]);
  const todayGames = useMemo(
    () =>
      games.filter((game) => {
        const today = new Date();
        const gameDate = new Date(game.scheduled_start_time);
        return gameDate.getFullYear() === today.getFullYear() && gameDate.getMonth() === today.getMonth() && gameDate.getDate() === today.getDate();
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

  const activeFollowedGameCount = useMemo(() => sortedGames.filter((game) => followedGameIds.has(game.id)).length, [sortedGames, followedGameIds]);

  const startingSoonCount = useMemo(() => {
    const now = new Date().getTime();
    const windowEnd = now + 3 * 60 * 60 * 1000;
    return sortedGames.filter((game) => {
      const ts = new Date(game.scheduled_start_time).getTime();
      return ts >= now && ts <= windowEnd && game.status !== "final";
    }).length;
  }, [sortedGames]);

  const visibleGames = useMemo(() => {
    let result = sortedGames;
    if (filter === "live") result = result.filter((game) => game.status === "in_progress" || game.status === "live");
    else if (filter === "today") result = result.filter((game) => todayGameIds.has(game.id));
    else if (filter === "following") result = result.filter((game) => followedGameIds.has(game.id));

    if (teamFilter !== "all") {
      result = result.filter((game) => game.home_team_id === teamFilter || game.away_team_id === teamFilter);
    }

    const q = query.trim().toLowerCase();
    if (!q) return result;

    return result.filter((game) => {
      const home = teamMap.get(game.home_team_id);
      const away = teamMap.get(game.away_team_id);
      const hay = `${home?.name ?? ""} ${home?.abbreviation ?? ""} ${away?.name ?? ""} ${away?.abbreviation ?? ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [sortedGames, filter, todayGameIds, followedGameIds, teamFilter, query, teamMap]);

  const watchedTeams = useMemo(
    () =>
      followedTeams
        .map((team) => ({
          team,
          activeCount: sortedGames.filter((game) => game.status !== "final" && (game.home_team_id === team.id || game.away_team_id === team.id)).length,
        }))
        .sort((a, b) => b.activeCount - a.activeCount || a.team.name.localeCompare(b.team.name)),
    [followedTeams, sortedGames],
  );

  const groupedVisibleGames: GameDayGroup[] = useMemo(() => {
    const groups = new Map<string, Game[]>();
    visibleGames.forEach((game) => {
      const label = new Date(game.scheduled_start_time).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
      const current = groups.get(label) ?? [];
      current.push(game);
      groups.set(label, current);
    });
    return Array.from(groups.entries()).map(([label, items]) => ({ label, items }));
  }, [visibleGames]);

  return (
    <section className="view-stack games-page">
      <div className="metric-grid">
        <article className="metric-card"><span>Live</span><strong>{liveGames.length}</strong></article>
        <article className="metric-card"><span>Starting Soon</span><strong>{startingSoonCount}</strong></article>
        <article className="metric-card"><span>Following</span><strong>{activeFollowedGameCount}</strong></article>
        <article className="metric-card"><span>Alerts Sent 24h</span><strong>{sentAlerts24h}</strong></article>
      </div>

      <section className="panel games-panel">
        <div className="section-header"><h3>Game Feed</h3><p>Track tipoff times, probabilities, and follow actions in one place.</p></div>
        <div className="toolbar unified-toolbar games-toolbar">
          <input placeholder="Search team or abbreviation" value={query} onChange={(event) => setQuery(event.target.value)} className="search-input" />
          <select value={teamFilter} onChange={(event) => setTeamFilter(event.target.value === "all" ? "all" : Number(event.target.value))}>
            <option value="all">All teams</option>
            {availableTeams.map((team) => <option key={team.id} value={team.id}>{team.name} ({team.abbreviation})</option>)}
          </select>
          <div className="chip-row">
            <button className={`chip-btn ${filter === "all" ? "active" : ""}`.trim()} onClick={() => setFilter("all")} disabled={isLoading}>All</button>
            <button className={`chip-btn ${filter === "live" ? "active" : ""}`.trim()} onClick={() => setFilter("live")} disabled={isLoading}>Live ({liveGames.length})</button>
            <button className={`chip-btn ${filter === "today" ? "active" : ""}`.trim()} onClick={() => setFilter("today")} disabled={isLoading}>Today ({todayGames.length})</button>
            <button className={`chip-btn ${filter === "following" ? "active" : ""}`.trim()} onClick={() => setFilter("following")} disabled={isLoading}>Following ({activeFollowedGameCount})</button>
          </div>
          <button className="btn btn-secondary games-refresh-btn" disabled={isLoading || toggleMutation.isPending} onClick={() => refetch().then(() => setLastSync(new Date())).catch((err) => setError(messageFromUnknown(err)))}>Refresh</button>
        </div>

        {error ? <p className="error">{error}</p> : null}
        {isLoading ? <p className="muted">Loading games...</p> : null}

        {!isLoading ? (
          <div className="games-feed-grid">
            <div className="data-table-wrap">
              <table className="games-table" role="table" aria-label="Games feed">
                <colgroup><col className="games-col-time" /><col className="games-col-matchup" /><col className="games-col-win" /><col className="games-col-odds" /><col className="games-col-action" /></colgroup>
                <thead><tr><th>Time</th><th>Matchup</th><th>Win %</th><th>Odds</th><th>Action</th></tr></thead>
                <tbody>
                  {groupedVisibleGames.map((group) => (
                    <Fragment key={group.label}>
                      <tr className="games-group-row"><td colSpan={5}><div className="games-group-row-inner"><strong>{group.label}</strong><span className="muted">{group.items.length} games</span></div></td></tr>
                      {group.items.map((game) => {
                        const home = teamMap.get(game.home_team_id);
                        const away = teamMap.get(game.away_team_id);
                        if (!home || !away) return null;
                        const isFollowed = followedGameIds.has(game.id);
                        const probabilities = noVigProbabilities(game);
                        const awayPercent = probabilities ? Math.round(probabilities.away * 100) : null;
                        const homePercent = awayPercent !== null ? 100 - awayPercent : null;
                        return (
                          <tr key={game.id} className="games-data-row"><td colSpan={5}><div className="games-data-row-grid">
                            <div className="games-time-cell">{game.status === "scheduled" ? new Date(game.scheduled_start_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : formatGameTime(game)}</div>
                            <div><div className="team-row"><TeamLogo team={away} size={24} /><strong>{away.abbreviation}</strong><span className="muted">@</span><TeamLogo team={home} size={24} /><strong>{home.abbreviation}</strong></div></div>
                            <div className="games-win-cell">{probabilities ? `${awayPercent}% / ${homePercent}%` : "—"}</div>
                            <div className="games-odds-cell">{game.odds ? <><span className="games-odds-main">{formatMoneyline(game.odds.away_moneyline)} / {formatMoneyline(game.odds.home_moneyline)}</span><span className="games-odds-book muted">{game.odds.bookmaker}</span></> : "—"}</div>
                            <div className="games-action-cell-wrap"><button className={`btn ${isFollowed ? "btn-secondary" : ""} games-action-cell`.trim()} disabled={toggleMutation.isPending} onClick={() => toggleMutation.mutate({ gameId: game.id, isFollowed })}>{isFollowed ? "Following" : "Follow"}</button></div>
                          </div></td></tr>
                        );
                      })}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            <aside className="games-side-rail"><section className="games-side-card"><div className="games-side-header"><h4>Watched Teams</h4><span className="muted">{watchedTeams.length}</span></div>{watchedTeams.length === 0 ? <p className="muted">No followed teams yet.</p> : <ul className="games-watch-list">{watchedTeams.map(({ team, activeCount }) => <li key={team.id}><div className="games-watch-team"><TeamLogo team={team} size={18} /><span>{team.name}</span></div><span className="games-watch-count">{activeCount}</span></li>)}</ul>}</section></aside>
          </div>
        ) : null}

        {!isLoading && visibleGames.length === 0 ? <p className="muted">No games in this filter.</p> : null}
      </section>
    </section>
  );
}
