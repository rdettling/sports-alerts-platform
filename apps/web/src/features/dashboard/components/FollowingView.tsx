import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followTeam, unfollowGame, unfollowTeam, type Game, type Team } from "../../../shared/api";
import { TeamLogo, formatTipoff, isGameActive, isRecentlyCompletedGame, messageFromUnknown, scoreSnippet } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";
import { useFollowingData } from "../hooks/useFollowingData";

export function FollowingView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();
  const queryClient = useQueryClient();
  const { data, isLoading, refetch } = useFollowingData(token);

  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [gamesTab, setGamesTab] = useState<"active" | "recent">("active");
  const [error, setError] = useState<string | null>(null);

  const allTeams = data?.teams ?? [];
  const follows = data?.follows;

  useEffect(() => {
    if (!selectedTeamId && allTeams.length > 0) {
      setSelectedTeamId(allTeams[0].id);
    }
  }, [allTeams, selectedTeamId]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["following-page", token] });
    setLastSync(new Date());
  };

  const unfollowGameMutation = useMutation({ mutationFn: async (gameId: number) => unfollowGame(token, gameId), onSuccess: invalidate, onError: (e) => setError(messageFromUnknown(e)) });
  const followTeamMutation = useMutation({ mutationFn: async (teamId: number) => followTeam(token, teamId), onSuccess: invalidate, onError: (e) => setError(messageFromUnknown(e)) });
  const unfollowTeamMutation = useMutation({ mutationFn: async (teamId: number) => unfollowTeam(token, teamId), onSuccess: invalidate, onError: (e) => setError(messageFromUnknown(e)) });

  const followedTeamIds = useMemo(() => new Set((follows?.teams ?? []).map((team) => team.id)), [follows?.teams]);
  const games = useMemo(() => [...(follows?.games ?? [])].sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()), [follows?.games]);
  const teamMap = useMemo(() => new Map(allTeams.map((team: Team) => [team.id, team])), [allTeams]);
  const followedTeams = useMemo(() => allTeams.filter((team) => followedTeamIds.has(team.id)), [allTeams, followedTeamIds]);
  const activeGames = useMemo(() => games.filter((game) => isGameActive(game)).sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()), [games]);
  const recentCompletedGames = useMemo(() => {
    const nowMs = new Date().getTime();
    return games.filter((game) => isRecentlyCompletedGame(game, nowMs)).sort((a, b) => new Date(b.scheduled_start_time).getTime() - new Date(a.scheduled_start_time).getTime());
  }, [games]);
  const shownGames = gamesTab === "active" ? activeGames : recentCompletedGames;

  return (
    <section className="view-stack">
      <section className="panel">
        <div className="section-header section-header-inline">
          <div><h3>Following Workspace</h3><p>Manage followed teams and quickly trim followed games.</p></div>
          <button className="btn btn-secondary" disabled={isLoading} onClick={() => refetch().then(() => setLastSync(new Date())).catch((err) => setError(messageFromUnknown(err)))}>Refresh</button>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {isLoading ? <p className="muted">Loading following data...</p> : null}

        {!isLoading ? (
          <div className="two-panel-grid">
            <article className="subpanel">
              <h4>Teams</h4>
              <div className="toolbar">
                <select value={selectedTeamId ?? ""} onChange={(event) => setSelectedTeamId(Number(event.target.value))}>
                  {allTeams.map((team) => <option key={team.id} value={team.id}>{team.name} ({team.abbreviation})</option>)}
                </select>
                <button className="btn" type="button" disabled={!selectedTeamId || followTeamMutation.isPending} onClick={() => selectedTeamId && followTeamMutation.mutate(selectedTeamId)}>Follow Team</button>
              </div>
              {followedTeams.length === 0 ? <p className="muted">No followed teams yet.</p> : null}
              <ul className="list">
                {followedTeams.map((team) => (
                  <li key={team.id} className="row-card">
                    <span className="team-row"><TeamLogo team={team} size={22} /><span>{team.name} <span className="muted">({team.abbreviation})</span></span></span>
                    <button className="btn btn-secondary" disabled={unfollowTeamMutation.isPending} onClick={() => unfollowTeamMutation.mutate(team.id)}>Unfollow</button>
                  </li>
                ))}
              </ul>
            </article>

            <article className="subpanel">
              <h4>Games</h4>
              <div className="chip-row">
                <button className={`chip-btn ${gamesTab === "active" ? "active" : ""}`.trim()} onClick={() => setGamesTab("active")}>Active ({activeGames.length})</button>
                <button className={`chip-btn ${gamesTab === "recent" ? "active" : ""}`.trim()} onClick={() => setGamesTab("recent")}>Recent 24h ({recentCompletedGames.length})</button>
              </div>
              {shownGames.length === 0 ? <p className="muted">{gamesTab === "active" ? "No active followed games." : "No recently completed followed games."}</p> : null}
              <ul className="list">
                {shownGames.map((game: Game) => {
                  const away = teamMap.get(game.away_team_id);
                  const home = teamMap.get(game.home_team_id);
                  if (!away || !home) return null;
                  return (
                    <li key={game.id} className="row-card">
                      <span className="team-row"><TeamLogo team={away} size={20} /><strong>{away.abbreviation}</strong><span className="muted">@</span><TeamLogo team={home} size={20} /><strong>{home.abbreviation}</strong><span className="muted">{!isGameActive(game) ? ` • ${scoreSnippet(game) || formatTipoff(game.scheduled_start_time)} • Final` : ` • ${formatTipoff(game.scheduled_start_time)}`}</span></span>
                      <button className="btn btn-secondary" disabled={unfollowGameMutation.isPending} onClick={() => unfollowGameMutation.mutate(game.id)}>Unfollow</button>
                    </li>
                  );
                })}
              </ul>
            </article>
          </div>
        ) : null}
      </section>
    </section>
  );
}
