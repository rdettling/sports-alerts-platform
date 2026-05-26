import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followTeam, unfollowGame, unfollowTeam, type Team } from "../../../shared/api";
import { TeamLogo, formatGameTime, formatMoneyline, isGameActive, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";
import { useFollowingData } from "../hooks/useFollowingData";

function leagueLogoUrl(league: string | null | undefined): string | null {
  const normalized = (league || "").toUpperCase();
  if (normalized === "NBA") return "https://cdn.nba.com/logos/leagues/logo-nba-logoman.svg";
  if (normalized === "MLB") return "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg";
  return null;
}

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
                  </article>
                );
              })}
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
