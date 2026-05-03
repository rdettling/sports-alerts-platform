import { useEffect, useMemo, useState } from "react";

import { followTeam, listFollows, listTeams, unfollowGame, unfollowTeam, type Game, type Team } from "../../../shared/api";
import { TeamLogo, formatTipoff, isGameActive, isRecentlyCompletedGame, messageFromUnknown, scoreSnippet } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";

export function FollowingView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [gamesTab, setGamesTab] = useState<"active" | "recent">("active");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [allTeams, setAllTeams] = useState<Team[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [followedTeamIds, setFollowedTeamIds] = useState<Set<number>>(new Set());
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);
  const [addingTeam, setAddingTeam] = useState(false);

  const load = async () => {
    setError(null);
    setIsLoading(true);
    try {
      const [follows, teams] = await Promise.all([listFollows(token), listTeams()]);
      setAllTeams(teams);
      setFollowedTeamIds(new Set(follows.teams.map((team) => team.id)));
      setGames([...follows.games].sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()));
      setLastSync(new Date());
    } catch (loadError) {
      setError(messageFromUnknown(loadError));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load().catch((loadError) => setError(messageFromUnknown(loadError)));
  }, [token]);

  useEffect(() => {
    const id = window.setInterval(() => {
      load().catch((loadError) => setError(messageFromUnknown(loadError)));
    }, 120_000);
    return () => window.clearInterval(id);
  }, [token]);

  useEffect(() => {
    if (!selectedTeamId && allTeams.length > 0) {
      setSelectedTeamId(allTeams[0].id);
    }
  }, [allTeams, selectedTeamId]);

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
          <button className="btn btn-secondary" disabled={isLoading || busyGameId !== null || addingTeam} onClick={() => load().catch((err) => setError(messageFromUnknown(err)))}>Refresh</button>
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
                <button
                  className="btn"
                  type="button"
                  disabled={!selectedTeamId || addingTeam}
                  onClick={async () => {
                    if (!selectedTeamId) return;
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
                  }}
                >
                  Follow Team
                </button>
              </div>
              {followedTeams.length === 0 ? <p className="muted">No followed teams yet.</p> : null}
              <ul className="list">
                {followedTeams.map((team) => (
                  <li key={team.id} className="row-card">
                    <span className="team-row"><TeamLogo team={team} size={22} /><span>{team.name} <span className="muted">({team.abbreviation})</span></span></span>
                    <button
                      className="btn btn-secondary"
                      disabled={busyTeamId === team.id}
                      onClick={async () => {
                        setError(null);
                        setBusyTeamId(team.id);
                        try {
                          await unfollowTeam(token, team.id);
                          await load();
                        } catch (requestError) {
                          setError(messageFromUnknown(requestError));
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
                      <button
                        className="btn btn-secondary"
                        disabled={busyGameId === game.id}
                        onClick={async () => {
                          setError(null);
                          setBusyGameId(game.id);
                          try {
                            await unfollowGame(token, game.id);
                            await load();
                          } catch (requestError) {
                            setError(messageFromUnknown(requestError));
                          } finally {
                            setBusyGameId(null);
                          }
                        }}
                      >
                        Unfollow
                      </button>
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
