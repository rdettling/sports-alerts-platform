import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { followTeam, type Competition, unfollowTeam } from "../../../shared/api";
import { TeamLogo } from "../../../shared/components/TeamLogo";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import {
  competitionVisibilityQueryOptions,
  competitionsQueryOptions,
  dashboardQueryKeys,
  followsQueryOptions,
  teamsQueryOptions,
} from "../hooks/dashboard-query-options";
import { CompetitionTabs, ConferenceSelect, ScopeToggle } from "./DashboardFilters";
import { fbsConferenceOptions } from "./fbs-conferences";

export function TeamsView({
  token,
  onSignInRequired,
  onManageLeagues,
}: {
  token: string | null;
  onSignInRequired: () => void;
  onManageLeagues: () => void;
}) {
  const queryClient = useQueryClient();
  const [teamScope, setTeamScope] = useState<"all" | "following">("all");
  const [competitionFilter, setCompetitionFilter] = useState<"all" | Competition>("all");
  const [conferenceFilter, setConferenceFilter] = useState<"all" | string>("all");
  const [teamSearch, setTeamSearch] = useState("");
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const teamsQuery = useQuery(teamsQueryOptions());
  const competitionsQuery = useQuery(competitionsQueryOptions());
  const competitionVisibilityQuery = useQuery(competitionVisibilityQueryOptions(token));
  const followsQuery = useQuery(followsQueryOptions(token));
  const teams = teamsQuery.data ?? [];
  const competitions = competitionsQuery.data ?? [];
  const competitionVisibility = competitionVisibilityQuery.data ?? { hidden_competitions: [] };
  const followedTeams = followsQuery.data?.teams ?? [];
  const isLoading =
    teamsQuery.isLoading ||
    competitionsQuery.isLoading ||
    competitionVisibilityQuery.isLoading ||
    followsQuery.isLoading;
  const queryError =
    teamsQuery.error ??
    competitionsQuery.error ??
    competitionVisibilityQuery.error ??
    followsQuery.error;

  const followedTeamIds = useMemo(
    () => new Set(followedTeams.map((team) => team.id)),
    [followedTeams],
  );
  const hiddenCompetitions = useMemo(
    () => new Set<Competition>(competitionVisibility.hidden_competitions),
    [competitionVisibility.hidden_competitions],
  );
  const visibleCompetitions = useMemo(
    () => competitions.filter(({ competition }) => !hiddenCompetitions.has(competition)),
    [competitions, hiddenCompetitions],
  );
  const visibleCompetitionIds = useMemo(
    () => new Set(visibleCompetitions.map(({ competition }) => competition)),
    [visibleCompetitions],
  );
  const visibilityFilteredTeams = useMemo(
    () =>
      teams.filter((team) =>
        team.competitions.some((competition) => visibleCompetitionIds.has(competition)),
      ),
    [teams, visibleCompetitionIds],
  );
  const visibleFollowedTeamCount = useMemo(
    () => visibilityFilteredTeams.filter((team) => followedTeamIds.has(team.id)).length,
    [followedTeamIds, visibilityFilteredTeams],
  );
  const conferenceOptions = useMemo(
    () => fbsConferenceOptions(visibilityFilteredTeams),
    [visibilityFilteredTeams],
  );

  useEffect(() => {
    if (!token && teamScope !== "all") setTeamScope("all");
  }, [teamScope, token]);

  useEffect(() => {
    if (
      competitionFilter !== "all" &&
      !visibleCompetitions.some((item) => item.competition === competitionFilter)
    ) {
      setCompetitionFilter("all");
    }
  }, [competitionFilter, visibleCompetitions]);

  useEffect(() => {
    if (
      competitionFilter !== "FBS" ||
      (conferenceFilter !== "all" && !conferenceOptions.includes(conferenceFilter))
    ) {
      setConferenceFilter("all");
    }
  }, [competitionFilter, conferenceFilter, conferenceOptions]);

  const visibleTeams = useMemo(() => {
    const search = teamSearch.trim().toLowerCase();
    return [...visibilityFilteredTeams]
      .filter(
        (team) => competitionFilter === "all" || team.competitions.includes(competitionFilter),
      )
      .filter(
        (team) =>
          competitionFilter !== "FBS" ||
          conferenceFilter === "all" ||
          team.conference === conferenceFilter,
      )
      .filter((team) => teamScope === "all" || followedTeamIds.has(team.id))
      .filter(
        (team) => !search || `${team.name} ${team.abbreviation}`.toLowerCase().includes(search),
      )
      .sort((a, b) => {
        const followedDifference =
          Number(followedTeamIds.has(b.id)) - Number(followedTeamIds.has(a.id));
        return followedDifference || a.name.localeCompare(b.name);
      });
  }, [
    visibilityFilteredTeams,
    followedTeamIds,
    competitionFilter,
    conferenceFilter,
    teamScope,
    teamSearch,
  ]);

  const teamGroups = useMemo(() => {
    if (visibleTeams.length === 0) return [];
    const selectedCompetition = visibleCompetitions.find(
      (item) => item.competition === competitionFilter,
    );
    return [
      {
        key: competitionFilter,
        label: selectedCompetition?.label ?? "All teams",
        teams: visibleTeams,
      },
    ];
  }, [competitionFilter, visibleCompetitions, visibleTeams]);
  const competitionLabels = useMemo(
    () => new Map(visibleCompetitions.map((item) => [item.competition, item.badge_label] as const)),
    [visibleCompetitions],
  );

  const toggleMutation = useMutation({
    mutationFn: async ({ teamId, isFollowed }: { teamId: number; isFollowed: boolean }) => {
      if (!token) return;
      if (isFollowed) await unfollowTeam(token, teamId);
      else await followTeam(token, teamId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.follows(token) });
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
            className={`filter-toolbar teams-filter-toolbar ${token ? "" : "without-scope"} ${competitionFilter === "FBS" ? "with-conference" : ""}`.trim()}
            aria-label="Team filters"
          >
            {token ? (
              <ScopeToggle
                ariaLabel="Team scope"
                allLabel="All teams"
                value={teamScope}
                followingCount={visibleFollowedTeamCount}
                onChange={setTeamScope}
              />
            ) : null}

            <CompetitionTabs
              ariaLabel="Competition filter"
              options={[
                { value: "all", label: "All" },
                ...visibleCompetitions.map((competition) => ({
                  value: competition.competition,
                  label: competition.label,
                })),
              ]}
              value={competitionFilter}
              onChange={setCompetitionFilter}
            />

            {competitionFilter === "FBS" ? (
              <ConferenceSelect
                options={conferenceOptions}
                value={conferenceFilter}
                onChange={setConferenceFilter}
              />
            ) : null}

            <input
              className="teams-search"
              type="search"
              aria-label="Search teams"
              placeholder="Search teams..."
              value={teamSearch}
              onChange={(event) => setTeamSearch(event.target.value)}
            />
          </section>

          <section className="teams-results-scroll" aria-label="Team directory">
            {teamGroups.length > 0 ? (
              <div className="teams-competition-list">
                {teamGroups.map((group, groupIndex) => {
                  const headingId = `teams-group-${groupIndex}`;
                  return (
                    <section
                      key={group.key}
                      className="teams-competition-board surface"
                      aria-labelledby={headingId}
                    >
                      <div className="teams-competition-header surface-header">
                        <h2 id={headingId}>{group.label}</h2>
                        <span>
                          {group.teams.length} {group.teams.length === 1 ? "team" : "teams"}
                        </span>
                      </div>
                      <ul className="teams-directory-grid">
                        {group.teams.map((team) => {
                          const isFollowed = followedTeamIds.has(team.id);
                          const metadata = [
                            team.abbreviation,
                            ...team.competitions
                              .filter(
                                (competition) =>
                                  visibleCompetitionIds.has(competition) &&
                                  competition !== competitionFilter,
                              )
                              .map(
                                (competition) => competitionLabels.get(competition) ?? competition,
                              ),
                          ].join(" · ");
                          return (
                            <li
                              key={team.id}
                              className={`team-directory-row ${isFollowed ? "followed" : ""}`.trim()}
                            >
                              <span className="team-directory-main">
                                <TeamLogo team={team} size={30} />
                                <span className="team-directory-copy">
                                  <strong title={team.name}>{team.name}</strong>
                                  <span className="team-directory-meta">{metadata}</span>
                                </span>
                              </span>
                              <button
                                className={`team-directory-action text-action ${isFollowed ? "following" : ""}`.trim()}
                                type="button"
                                aria-pressed={isFollowed}
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
                                    ? "Following"
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
              <div className="muted view-feedback empty-visibility-state">
                <p>
                  {visibleCompetitions.length === 0
                    ? "No leagues are currently shown."
                    : teamScope === "following"
                      ? "No followed teams match this filter."
                      : "No teams match this filter."}
                </p>
                {token && visibleCompetitions.length === 0 ? (
                  <button className="btn" type="button" onClick={onManageLeagues}>
                    Choose leagues
                  </button>
                ) : null}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </section>
  );
}
