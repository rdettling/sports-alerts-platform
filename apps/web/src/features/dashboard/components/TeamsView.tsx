import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { followTeam, type Competition, unfollowTeam } from "../../../shared/api";
import { TeamLogo } from "../../../shared/components/TeamLogo";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import {
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
}: {
  token: string | null;
  onSignInRequired: () => void;
}) {
  const queryClient = useQueryClient();
  const [teamScope, setTeamScope] = useState<"all" | "following">("all");
  const [competitionFilter, setCompetitionFilter] = useState<"all" | Competition>("all");
  const [conferenceFilter, setConferenceFilter] = useState<"all" | string>("all");
  const [teamSearch, setTeamSearch] = useState("");
  const [expandedConferences, setExpandedConferences] = useState<Set<string>>(new Set());
  const [busyTeamId, setBusyTeamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const teamsQuery = useQuery(teamsQueryOptions());
  const competitionsQuery = useQuery(competitionsQueryOptions());
  const followsQuery = useQuery(followsQueryOptions(token));
  const teams = teamsQuery.data ?? [];
  const competitions = competitionsQuery.data ?? [];
  const followedTeams = followsQuery.data?.teams ?? [];
  const isLoading = teamsQuery.isLoading || competitionsQuery.isLoading || followsQuery.isLoading;
  const queryError = teamsQuery.error ?? competitionsQuery.error ?? followsQuery.error;

  const followedTeamIds = useMemo(
    () => new Set(followedTeams.map((team) => team.id)),
    [followedTeams],
  );
  const conferenceOptions = useMemo(() => fbsConferenceOptions(teams), [teams]);

  useEffect(() => {
    if (!token && teamScope !== "all") setTeamScope("all");
  }, [teamScope, token]);

  useEffect(() => {
    if (
      competitionFilter !== "all" &&
      !competitions.some((item) => item.competition === competitionFilter)
    ) {
      setCompetitionFilter("all");
    }
  }, [competitionFilter, competitions]);

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
    return [...teams]
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
  }, [teams, followedTeamIds, competitionFilter, conferenceFilter, teamScope, teamSearch]);

  const teamGroups = useMemo(() => {
    if (visibleTeams.length === 0) return [];
    const selectedCompetition = competitions.find((item) => item.competition === competitionFilter);
    if (competitionFilter === "FBS") {
      const followedTeams = visibleTeams.filter((team) => followedTeamIds.has(team.id));
      const grouped = new Map<string, typeof visibleTeams>();
      visibleTeams.forEach((team) => {
        const key = team.conference ?? "OTHER";
        grouped.set(key, [...(grouped.get(key) ?? []), team]);
      });
      return [
        ...(followedTeams.length
          ? [{ key: "following", label: "Following", teams: followedTeams, collapsible: false }]
          : []),
        ...conferenceOptions
          .filter((conference) => grouped.has(conference))
          .map((conference) => ({
            key: conference,
            label: conference,
            teams: grouped.get(conference) ?? [],
            collapsible: true,
          })),
        ...(grouped.has("OTHER")
          ? [
              {
                key: "OTHER",
                label: "Other opponents",
                teams: grouped.get("OTHER") ?? [],
                collapsible: true,
              },
            ]
          : []),
      ];
    }
    return [
      {
        key: competitionFilter,
        label: selectedCompetition?.label ?? "All teams",
        teams: visibleTeams,
        collapsible: false,
      },
    ];
  }, [competitionFilter, competitions, conferenceOptions, followedTeamIds, visibleTeams]);
  const competitionLabels = useMemo(
    () => new Map(competitions.map((item) => [item.competition, item.badge_label] as const)),
    [competitions],
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
                followingCount={followedTeamIds.size}
                onChange={setTeamScope}
              />
            ) : null}

            <CompetitionTabs
              ariaLabel="Competition filter"
              options={[
                { value: "all", label: "All" },
                ...competitions.map((competition) => ({
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

            <p className="teams-helper">Following a team follows its games automatically.</p>
          </section>

          <section className="teams-results-scroll" aria-label="Team directory">
            {teamGroups.length > 0 ? (
              <div className="teams-competition-list">
                {teamGroups.map((group, groupIndex) => {
                  const headingId = `teams-group-${groupIndex}`;
                  const canCollapse =
                    group.collapsible && conferenceFilter === "all" && !teamSearch.trim();
                  const isExpanded = !canCollapse || expandedConferences.has(group.key);
                  return (
                    <section
                      key={group.key}
                      className="teams-competition-board surface"
                      aria-labelledby={headingId}
                    >
                      <div className="teams-competition-header surface-header">
                        <h2 id={headingId}>
                          {canCollapse ? (
                            <button
                              className="teams-group-toggle"
                              type="button"
                              aria-expanded={isExpanded}
                              onClick={() =>
                                setExpandedConferences((current) => {
                                  const next = new Set(current);
                                  if (isExpanded) next.delete(group.key);
                                  else next.add(group.key);
                                  return next;
                                })
                              }
                            >
                              <span aria-hidden>{isExpanded ? "−" : "+"}</span>
                              {group.label}
                            </button>
                          ) : (
                            group.label
                          )}
                        </h2>
                        <span>
                          {group.teams.length} {group.teams.length === 1 ? "team" : "teams"}
                        </span>
                      </div>
                      {isExpanded ? (
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
                                    <span className="team-directory-meta">
                                      <span>{team.abbreviation}</span>
                                      {team.competitions.map((competition) => (
                                        <span className="team-competition-badge" key={competition}>
                                          {competitionLabels.get(competition) ?? competition}
                                        </span>
                                      ))}
                                    </span>
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
                      ) : null}
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
