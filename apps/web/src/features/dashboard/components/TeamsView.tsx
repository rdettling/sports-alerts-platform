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
import { TeamLogo } from "../../../shared/components/TeamLogo";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { LeagueTabs, ScopeToggle } from "./DashboardFilters";

const EMPTY_FOLLOWS: CurrentFollows = { teams: [], games: [] };

export function TeamsView({
  token,
  onSignInRequired,
}: {
  token: string | null;
  onSignInRequired: () => void;
}) {
  const queryClient = useQueryClient();
  const [teamScope, setTeamScope] = useState<"all" | "following">("all");
  const [leagueFilter, setLeagueFilter] = useState<"all" | League>("all");
  const [teamSearch, setTeamSearch] = useState("");
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    data,
    isLoading,
    error: queryError,
  } = useQuery({
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
  const followedTeamIds = useMemo(
    () => new Set((data?.follows.teams ?? []).map((team) => team.id)),
    [data?.follows.teams],
  );

  useEffect(() => {
    if (!token && teamScope !== "all") setTeamScope("all");
  }, [teamScope, token]);

  useEffect(() => {
    if (leagueFilter !== "all" && !leagues.some((item) => item.league === leagueFilter)) {
      setLeagueFilter("all");
    }
  }, [leagueFilter, leagues]);

  const visibleTeams = useMemo(() => {
    const search = teamSearch.trim().toLowerCase();
    return [...(data?.teams ?? [])]
      .filter((team) => leagueFilter === "all" || team.league === leagueFilter)
      .filter((team) => teamScope === "all" || followedTeamIds.has(team.id))
      .filter(
        (team) => !search || `${team.name} ${team.abbreviation}`.toLowerCase().includes(search),
      )
      .sort((a, b) => {
        const followedDifference =
          Number(followedTeamIds.has(b.id)) - Number(followedTeamIds.has(a.id));
        return followedDifference || a.name.localeCompare(b.name);
      });
  }, [data?.teams, followedTeamIds, leagueFilter, teamScope, teamSearch]);

  const teamGroups = useMemo(
    () =>
      leagues
        .filter((league) => leagueFilter === "all" || league.league === leagueFilter)
        .map((league) => ({
          league: league.league,
          label: league.label,
          teams: visibleTeams.filter((team) => team.league === league.league),
        }))
        .filter((group) => group.teams.length > 0),
    [leagueFilter, leagues, visibleTeams],
  );

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
    <section className="view-stack teams-page" aria-label="Teams">
      {error || queryError ? (
        <p className="error view-feedback" role="alert">
          {error ?? messageFromUnknown(queryError)}
        </p>
      ) : null}
      {isLoading ? (
        <p className="muted view-feedback" role="status">
          Loading teams...
        </p>
      ) : null}

      {!isLoading ? (
        <div className="teams-layout">
          <section
            className={`filter-toolbar teams-filter-toolbar ${token ? "" : "without-scope"}`.trim()}
            aria-label="Team filters"
          >
            {token ? (
              <ScopeToggle
                ariaLabel="Team scope"
                allLabel="All teams"
                value={teamScope}
                followingCount={followedTeamIds.size}
                onChange={setTeamScope}
              />
            ) : null}

            <LeagueTabs
              ariaLabel="League filter"
              options={[
                { value: "all", label: "All" },
                ...leagues.map((league) => ({
                  value: league.league,
                  label: league.label,
                })),
              ]}
              value={leagueFilter}
              onChange={setLeagueFilter}
            />

            <input
              className="teams-search"
              type="search"
              aria-label="Search teams"
              placeholder="Search teams..."
              value={teamSearch}
              onChange={(event) => setTeamSearch(event.target.value)}
            />

            <p className="teams-helper">Following a team follows its games automatically.</p>
          </section>

          <section className="teams-results-scroll" aria-label="Team directory">
            {teamGroups.length > 0 ? (
              <div className="teams-league-list">
                {teamGroups.map((group) => {
                  const headingId = `teams-league-${group.league.toLowerCase()}`;
                  return (
                    <section
                      key={group.league}
                      className="teams-league-board surface"
                      aria-labelledby={headingId}
                    >
                      <div className="teams-league-header surface-header">
                        <h2 id={headingId}>{group.label}</h2>
                        <span>
                          {group.teams.length} {group.teams.length === 1 ? "team" : "teams"}
                        </span>
                      </div>
                      <ul className="teams-directory-grid">
                        {group.teams.map((team) => {
                          const isFollowed = followedTeamIds.has(team.id);
                          return (
                            <li
                              key={team.id}
                              className={`team-directory-row ${isFollowed ? "followed" : ""}`.trim()}
                            >
                              <span className="team-directory-main">
                                <TeamLogo team={team} size={30} />
                                <span className="team-directory-copy">
                                  <strong title={team.name}>{team.name}</strong>
                                  <span>{team.abbreviation}</span>
                                </span>
                              </span>
                              <button
                                className="team-directory-action text-action"
                                type="button"
                                disabled={busyTeamId === team.id || toggleMutation.isPending}
                                onClick={async () => {
                                  if (!token) {
                                    onSignInRequired();
                                    return;
                                  }
                                  setError(null);
                                  setBusyTeamId(team.id);
                                  try {
                                    await toggleMutation.mutateAsync({
                                      teamId: team.id,
                                      isFollowed,
                                    });
                                  } finally {
                                    setBusyTeamId(null);
                                  }
                                }}
                              >
                                {busyTeamId === team.id
                                  ? "Saving..."
                                  : isFollowed
                                    ? "Unfollow"
                                    : "Follow"}
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </section>
                  );
                })}
              </div>
            ) : (
              <p className="muted view-feedback">
                {teamScope === "following"
                  ? "No followed teams match this filter."
                  : "No teams match this filter."}
              </p>
            )}
          </section>
        </div>
      ) : null}
    </section>
  );
}
