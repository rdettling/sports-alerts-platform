import { type OpsAdminSummaryResponse } from "../../../../shared/api";

export type LeagueJobGroup = {
  league: OpsAdminSummaryResponse["runtime"]["league_settings"][number];
  catalogJob: OpsAdminSummaryResponse["runtime"]["jobs"][number] | null;
  liveJob: OpsAdminSummaryResponse["runtime"]["jobs"][number] | null;
};

export function buildLeagueJobGroups(summary: OpsAdminSummaryResponse): LeagueJobGroup[] {
  const enabledLeagues = summary.runtime.league_settings.filter((item) => item.is_enabled);
  const jobsByLeague = new Map(
    summary.runtime.jobs
      .filter((job) => job.league)
      .map((job) => [`${job.league}:${job.job_type}`, job] as const),
  );

  return enabledLeagues.map((league) => ({
    league,
    catalogJob: jobsByLeague.get(`${league.league}:catalog_sync`) ?? null,
    liveJob: jobsByLeague.get(`${league.league}:live_sync`) ?? null,
  }));
}
