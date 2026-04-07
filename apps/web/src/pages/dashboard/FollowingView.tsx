import { useEffect, useMemo, useState } from "react";

import { Game, Team, followTeam, listFollows, listTeams, unfollowGame, unfollowTeam } from "../../api";
import {
  TeamLogo,
  formatTipoff,
  isGameActive,
  isRecentlyCompletedGame,
  messageFromUnknown,
  scoreSnippet,
} from "./shared";

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
