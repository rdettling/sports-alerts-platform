import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  followLeague,
  followTeam,
  type League,
  unfollowGame,
  unfollowLeague,
  unfollowTeam,
  type Team,
} from "../../../shared/api";
import { TeamLogo, formatGameTime, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { formatGameStatusLabel } from "../utils/telemetry-format";
import { useFollowingData } from "../hooks/useFollowingData";
import { GameRowCard } from "./GameRowCard";
import { useGameAlertSettings } from "../hooks/useGameAlertSettings";
import { GameAlertSettingsModal } from "./GameAlertSettingsModal";

export function FollowingView({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, error: queryError } = useFollowingData(token);

  const [teamSearch, setTeamSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);
  const { alertGame, gameAlertState, alertsBusy, openGameAlerts, closeGameAlerts, applyAlertOverride } =
    useGameAlertSettings(token, setError);

  const teams = data?.teams ?? [];
  const followedTeams = data?.follows.teams ?? [];
  const followedLeagues = data?.follows.leagues ?? [];
  const followedGames = data?.games ?? [];

  useEffect(() => {
    if (queryError) setError(messageFromUnknown(queryError));
  }, [queryError]);

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

  const followLeagueMutation = useMutation({
    mutationFn: (league: League) => followLeague(token, league),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["following-page", token] });
      await queryClient.invalidateQueries({ queryKey: ["updates-page", token] });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const unfollowLeagueMutation = useMutation({
    mutationFn: (league: League) => unfollowLeague(token, league),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["following-page", token] });
      await queryClient.invalidateQueries({ queryKey: ["updates-page", token] });
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
            <h4>Followed Leagues ({followedLeagues.length})</h4>
            <div className="chip-row">
              {(["NBA", "MLB"] as League[]).map((league) => {
                const isFollowed = followedLeagues.some((item) => item.league === league);
                return (
                  <button
                    key={league}
                    className={`chip-btn ${isFollowed ? "active" : ""}`.trim()}
                    type="button"
                    disabled={followLeagueMutation.isPending || unfollowLeagueMutation.isPending}
                    onClick={async () => {
                      if (isFollowed) {
                        await unfollowLeagueMutation.mutateAsync(league);
                      } else {
                        await followLeagueMutation.mutateAsync(league);
                      }
                    }}
                  >
                    {isFollowed ? `${league} Following` : `Follow ${league}`}
                  </button>
                );
              })}
            </div>
          </section>

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

                return (
                  <GameRowCard
                    key={game.id}
                    game={game}
                    home={home}
                    away={away}
                    isFollowed
                    statusLabel={formatGameStatusLabel(game.status, game.status === "final" || game.is_final, formatGameTime(game))}
                    actionsDisabled={busyGameId === game.id || unfollowGameMutation.isPending}
                    onOpenAlertSettings={() => {
                      openGameAlerts(game).catch(() => undefined);
                    }}
                    onUnfollow={async () => {
                      setBusyGameId(game.id);
                      try {
                        await unfollowGameMutation.mutateAsync(game.id);
                      } finally {
                        setBusyGameId(null);
                      }
                    }}
                  />
                );
              })}
            </div>
          </section>
        </div>
      ) : null}

      <GameAlertSettingsModal
        isOpen={Boolean(alertGame)}
        matchupLabel={`${teamMap.get(alertGame?.away_team_id ?? -1)?.abbreviation ?? "AWAY"} @ ${teamMap.get(alertGame?.home_team_id ?? -1)?.abbreviation ?? "HOME"}`}
        alertsBusy={alertsBusy}
        gameAlertState={gameAlertState}
        onClose={closeGameAlerts}
        onApplyAlertOverride={applyAlertOverride}
      />
    </section>
  );
}
