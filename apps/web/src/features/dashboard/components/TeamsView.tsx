import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  followTeam,
  listFollows,
  listLeagues,
  listTeams,
  type CurrentFollows,
  type League,
  unfollowTeam,
} from "../../../shared/api";
import { TeamLogo, messageFromUnknown } from "../../../shared/lib/dashboard-ui";

const EMPTY_FOLLOWS: CurrentFollows = { teams: [], games: [] };

export function TeamsView({
  token,
  onSignInRequired,
}: {
  token: string | null;
  onSignInRequired: () => void;
}) {
  const queryClient = useQueryClient();
  const [leagueFilter, setLeagueFilter] = useState<"all" | League | null>(null);
  const [teamSearch, setTeamSearch] = useState("");
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: queryError } = useQuery({
    queryKey: ["teams-page", token ?? "anonymous"],
    queryFn: async () => {
      const [teams, leagues, follows] = await Promise.all([
        listTeams(),
        listLeagues(),
        token ? listFollows(token) : Promise.resolve(EMPTY_FOLLOWS),
      ]);
      return { teams, leagues, follows };
    },
    refetchInterval: 120_000,
  });

  const leagues = data?.leagues ?? [];
  const activeLeagueKeys = leagues.map((league) => league.league);

  useEffect(() => {
    if (activeLeagueKeys.length === 0) return;
    if (leagueFilter === null || (leagueFilter !== "all" && !activeLeagueKeys.includes(leagueFilter))) {
      setLeagueFilter(activeLeagueKeys[0]);
    }
  }, [activeLeagueKeys, leagueFilter]);

  const followedTeamIds = useMemo(
    () => new Set((data?.follows.teams ?? []).map((team) => team.id)),
    [data?.follows.teams],
  );
  const visibleTeams = useMemo(() => {
    const search = teamSearch.trim().toLowerCase();
    return [...(data?.teams ?? [])]
      .filter((team) => leagueFilter === "all" || leagueFilter === null || team.league === leagueFilter)
      .filter((team) => !search || `${team.name} ${team.abbreviation}`.toLowerCase().includes(search))
      .sort((a, b) => {
        const followedDifference = Number(followedTeamIds.has(b.id)) - Number(followedTeamIds.has(a.id));
        return followedDifference || a.name.localeCompare(b.name);
      });
  }, [data?.teams, followedTeamIds, leagueFilter, teamSearch]);

  const toggleMutation = useMutation({
    mutationFn: async ({ teamId, isFollowed }: { teamId: number; isFollowed: boolean }) => {
      if (!token) return;
      if (isFollowed) await unfollowTeam(token, teamId);
      else await followTeam(token, teamId);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["teams-page", token] }),
        queryClient.invalidateQueries({ queryKey: ["games-page", token] }),
      ]);
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  return (
    <section className="view-stack teams-page">
      <section className="panel teams-panel">
        <div className="teams-controls">
          <p className="teams-helper">Follow a team to follow all its games by default.</p>

          {!isLoading ? (
            <div className="teams-toolbar" role="group" aria-label="Team filters">
              <div className="teams-league-filter" role="group" aria-label="League filter">
                <button
                  className={`chip-btn ${leagueFilter === "all" ? "active" : ""}`.trim()}
                  type="button"
                  aria-pressed={leagueFilter === "all"}
                  onClick={() => setLeagueFilter("all")}
                >
                  All
                </button>
                {leagues.map((league) => (
                  <button
                    key={league.league}
                    className={`chip-btn ${leagueFilter === league.league ? "active" : ""}`.trim()}
                    type="button"
                    aria-pressed={leagueFilter === league.league}
                    onClick={() => setLeagueFilter(league.league)}
                  >
                    {league.label}
                  </button>
                ))}
              </div>
              <input
                type="search"
                aria-label="Search teams"
                placeholder="Search teams..."
                value={teamSearch}
                onChange={(event) => setTeamSearch(event.target.value)}
              />
            </div>
          ) : null}
        </div>

        <div className="teams-results-scroll">
          {error || queryError ? <p className="error">{error ?? messageFromUnknown(queryError)}</p> : null}
          {isLoading ? <p className="muted">Loading teams...</p> : null}

          {!isLoading ? (
            <>
              {visibleTeams.length === 0 ? <p className="muted">No teams match this filter.</p> : null}
              <ul className="teams-grid">
                {visibleTeams.map((team) => {
                  const isFollowed = followedTeamIds.has(team.id);
                  return (
                    <li key={team.id} className="row-card teams-row">
                      <span className="teams-row-main">
                        <TeamLogo team={team} size={28} />
                        <span>
                          <strong>{team.name}</strong>
                          <span className="muted teams-abbreviation">{team.abbreviation}</span>
                        </span>
                      </span>
                      <button
                        className={`btn ${isFollowed ? "btn-secondary" : ""}`.trim()}
                        type="button"
                        disabled={busyTeamId === team.id || toggleMutation.isPending}
                        onClick={async () => {
                          if (!token) {
                            onSignInRequired();
                            return;
                          }
                          setBusyTeamId(team.id);
                          try {
                            await toggleMutation.mutateAsync({ teamId: team.id, isFollowed });
                          } finally {
                            setBusyTeamId(null);
                          }
                        }}
                      >
                        {busyTeamId === team.id ? "Saving..." : isFollowed ? "Unfollow" : "Follow"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          ) : null}
        </div>
      </section>
    </section>
  );
}
