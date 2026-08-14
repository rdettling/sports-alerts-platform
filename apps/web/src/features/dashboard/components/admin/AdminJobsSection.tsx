import { useEffect, useState } from "react";

import { type OpsAdminSummaryResponse } from "../../../../shared/api";
import { LeagueTabs } from "../DashboardFilters";
import { formatAdminDateTime } from "./admin-format";
import { buildLeagueJobGroups, type LeagueJobGroup } from "./admin-jobs";

type RuntimeJob = LeagueJobGroup["catalogJob"];

function JobRow({ title, job }: { title: string; job: RuntimeJob }) {
  const isIssue = Boolean(
    job?.last_error ||
    job?.backoff_until ||
    job?.status === "error" ||
    job?.status === "failed" ||
    !job,
  );

  return (
    <article className={`admin-job-row ${isIssue ? "has-issue" : ""}`.trim()}>
      <div className="admin-job-main">
        <strong>{title}</strong>
        <span className={`admin-status ${isIssue ? "is-danger" : ""}`.trim()}>
          {job?.status ?? "missing"}
        </span>
      </div>
      <dl className="admin-job-metrics">
        <div>
          <dt>Next sync</dt>
          <dd>{formatAdminDateTime(job?.next_run_at)}</dd>
        </div>
        <div>
          <dt>Previous success</dt>
          <dd>{formatAdminDateTime(job?.last_success_at)}</dd>
        </div>
        {job?.backoff_until ? (
          <div className="is-danger">
            <dt>Backoff until</dt>
            <dd>{formatAdminDateTime(job.backoff_until)}</dd>
          </div>
        ) : null}
      </dl>
      {job?.last_error ? <p className="admin-job-error">{job.last_error}</p> : null}
    </article>
  );
}

export function AdminJobsSection({ summary }: { summary: OpsAdminSummaryResponse }) {
  const groups = buildLeagueJobGroups(summary);
  const [selectedLeague, setSelectedLeague] = useState(groups[0]?.league.league ?? "");

  useEffect(() => {
    if (!groups.some(({ league }) => league.league === selectedLeague)) {
      setSelectedLeague(groups[0]?.league.league ?? "");
    }
  }, [groups, selectedLeague]);

  const activeGroup =
    groups.find(({ league }) => league.league === selectedLeague) ?? groups[0] ?? null;

  return (
    <section className="admin-panel admin-jobs-panel surface" aria-labelledby="admin-jobs-title">
      <div className="admin-panel-header admin-jobs-header surface-header">
        <div>
          <h2 id="admin-jobs-title">Jobs</h2>
          <p>Catalog and live synchronization for enabled leagues.</p>
        </div>
        {groups.length ? (
          <LeagueTabs
            ariaLabel="Job league"
            options={groups.map(({ league }) => ({ value: league.league, label: league.label }))}
            value={activeGroup?.league.league ?? null}
            onChange={setSelectedLeague}
          />
        ) : null}
      </div>
      {activeGroup ? (
        <div className="admin-job-list">
          <JobRow title="Catalog Sync" job={activeGroup.catalogJob} />
          <JobRow title="Live Sync" job={activeGroup.liveJob} />
        </div>
      ) : (
        <p className="admin-panel-message muted">No enabled leagues are available.</p>
      )}
    </section>
  );
}
